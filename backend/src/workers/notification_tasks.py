"""Celery tasks for in-app and webhook notifications (Slack / Discord)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_session_factory():
    """Create a fresh async session factory bound to the current event loop."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from src.config import get_settings

    settings = get_settings()
    engine = create_async_engine(
        settings.postgres_dsn,
        echo=False,
        pool_size=3,
        max_overflow=1,
        pool_pre_ping=True,
    )
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# Webhook helper
# ---------------------------------------------------------------------------


async def _send_webhook(url: str, text: str) -> None:
    """POST a simple text message to a Slack-compatible or Discord webhook."""
    if not url:
        return
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            payload = {"text": text} if "slack" in url else {"content": text}
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status not in (200, 204):
                    body = await resp.text()
                    await log.awarn(
                        "webhook_non_200",
                        url=url[:60],
                        status=resp.status,
                        body=body[:200],
                    )
    except Exception as exc:
        await log.awarn("webhook_send_failed", url=url[:60], error=str(exc))


async def _create_notification(
    db: Any,
    user_id: uuid.UUID,
    type_: str,
    title: str,
    body: str | None,
    entity_type: str | None,
    entity_id: str | None,
) -> None:
    from src.adapters.db.pentest_extras_models import NotificationModel

    notification = NotificationModel(
        id=uuid.uuid4(),
        user_id=user_id,
        type=type_,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
        read=False,
        created_at=_utcnow(),
    )
    db.add(notification)


async def _get_engagement_user_ids(db: Any, engagement_id: uuid.UUID) -> list[uuid.UUID]:
    """Return the creator of the engagement as the sole notifiable user for now."""
    from sqlalchemy import select

    from src.adapters.db.pentest_models import EngagementModel

    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    if engagement is None:
        return []
    return [engagement.created_by]


# ---------------------------------------------------------------------------
# notify_critical_finding
# ---------------------------------------------------------------------------


@celery_app.task(name="pentest.notify_critical_finding", queue="pentest_light")
def notify_critical_finding(finding_id: str) -> dict[str, Any]:
    """Create in-app notifications and send webhooks for a critical/high finding."""
    return _run_async(_async_notify_critical_finding(finding_id))


async def _async_notify_critical_finding(finding_id: str) -> dict[str, Any]:
    from sqlalchemy import select

    from src.adapters.db.pentest_models import PentestFindingModel
    from src.config import get_settings

    settings = get_settings()
    session_factory = _make_session_factory()
    notified: list[str] = []

    async with session_factory() as db:
        stmt = select(PentestFindingModel).where(
            PentestFindingModel.id == uuid.UUID(finding_id)
        )
        finding = (await db.execute(stmt)).scalar_one_or_none()
        if finding is None:
            await log.aerror("notify_critical_finding_not_found", finding_id=finding_id)
            return {"error": "finding not found"}

        title = f"Critical finding: {finding.title}"
        body = (
            f"Severity: {finding.severity or 'unknown'} | "
            f"Finding UID: {finding.uid} | "
            f"Status: {finding.status}"
        )
        message = f"[PentAI] {title}\n{body}"

        user_ids = await _get_engagement_user_ids(db, finding.engagement_id)
        for user_id in user_ids:
            await _create_notification(
                db=db,
                user_id=user_id,
                type_="finding_critical",
                title=title,
                body=body,
                entity_type="finding",
                entity_id=finding_id,
            )
            notified.append(str(user_id))

        await db.commit()

    await _send_webhook(settings.slack_webhook_url, message)
    await _send_webhook(settings.discord_webhook_url, message)

    await log.ainfo(
        "notify_critical_finding_sent",
        finding_id=finding_id,
        notified_users=len(notified),
    )
    return {"finding_id": finding_id, "notified_users": notified}


# ---------------------------------------------------------------------------
# notify_scan_complete
# ---------------------------------------------------------------------------


@celery_app.task(name="pentest.notify_scan_complete", queue="pentest_light")
def notify_scan_complete(scan_id: str) -> dict[str, Any]:
    """Notify the engagement owner when a scan finishes."""
    return _run_async(_async_notify_scan_complete(scan_id))


async def _async_notify_scan_complete(scan_id: str) -> dict[str, Any]:
    from sqlalchemy import select

    from src.adapters.db.pentest_models import PentestFindingModel, PentestScanModel
    from src.config import get_settings

    settings = get_settings()
    session_factory = _make_session_factory()
    notified: list[str] = []

    async with session_factory() as db:
        stmt = select(PentestScanModel).where(PentestScanModel.id == uuid.UUID(scan_id))
        scan = (await db.execute(stmt)).scalar_one_or_none()
        if scan is None:
            await log.aerror("notify_scan_complete_not_found", scan_id=scan_id)
            return {"error": "scan not found"}

        # Count findings
        count_stmt = select(PentestFindingModel).where(PentestFindingModel.scan_id == scan.id)
        findings = (await db.execute(count_stmt)).scalars().all()
        findings_count = len(findings)

        title = f"Scan complete — {findings_count} finding(s) discovered"
        body = f"Scan ID: {scan_id} | Profile: {scan.profile} | Status: {scan.status}"
        message = f"[PentAI] {title}\n{body}"

        user_ids = await _get_engagement_user_ids(db, scan.engagement_id)
        # Also notify the scan requester
        if scan.user_id not in user_ids:
            user_ids.append(scan.user_id)

        for user_id in user_ids:
            await _create_notification(
                db=db,
                user_id=user_id,
                type_="scan_complete",
                title=title,
                body=body,
                entity_type="scan",
                entity_id=scan_id,
            )
            notified.append(str(user_id))

        await db.commit()

    await _send_webhook(settings.slack_webhook_url, message)
    await _send_webhook(settings.discord_webhook_url, message)

    await log.ainfo("notify_scan_complete_sent", scan_id=scan_id, notified_users=len(notified))
    return {"scan_id": scan_id, "notified_users": notified}


# ---------------------------------------------------------------------------
# notify_sla_breach
# ---------------------------------------------------------------------------


@celery_app.task(name="pentest.notify_sla_breach", queue="pentest_light")
def notify_sla_breach(finding_id: str) -> dict[str, Any]:
    """Notify the engagement owner that a finding has breached its SLA deadline."""
    return _run_async(_async_notify_sla_breach(finding_id))


async def _async_notify_sla_breach(finding_id: str) -> dict[str, Any]:
    from sqlalchemy import select

    from src.adapters.db.pentest_models import PentestFindingModel
    from src.config import get_settings

    settings = get_settings()
    session_factory = _make_session_factory()
    notified: list[str] = []

    async with session_factory() as db:
        stmt = select(PentestFindingModel).where(
            PentestFindingModel.id == uuid.UUID(finding_id)
        )
        finding = (await db.execute(stmt)).scalar_one_or_none()
        if finding is None:
            await log.aerror("notify_sla_breach_not_found", finding_id=finding_id)
            return {"error": "finding not found"}

        sla_str = finding.sla_due_at.isoformat() if finding.sla_due_at else "unknown"
        title = f"SLA breach: {finding.title}"
        body = (
            f"Severity: {finding.severity or 'unknown'} | "
            f"SLA due: {sla_str} | "
            f"Status: {finding.status} | "
            f"Finding UID: {finding.uid}"
        )
        message = f"[PentAI] SLA BREACH — {title}\n{body}"

        user_ids = await _get_engagement_user_ids(db, finding.engagement_id)
        for user_id in user_ids:
            await _create_notification(
                db=db,
                user_id=user_id,
                type_="sla_breach",
                title=title,
                body=body,
                entity_type="finding",
                entity_id=finding_id,
            )
            notified.append(str(user_id))

        await db.commit()

    await _send_webhook(settings.slack_webhook_url, message)
    await _send_webhook(settings.discord_webhook_url, message)

    await log.ainfo("notify_sla_breach_sent", finding_id=finding_id, notified_users=len(notified))
    return {"finding_id": finding_id, "notified_users": notified}
