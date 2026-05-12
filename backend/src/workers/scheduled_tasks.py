"""Celery beat tasks: scheduled re-scans, anomaly detection, quota reset, result cleanup."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from src.workers.celery_app import celery_app
from src.utils.time import utcnow

log = structlog.get_logger(__name__)


def _run_async(coro):
    return asyncio.run(coro)


def _session_factory():
    """Return the shared async session factory (avoids creating a new engine per task)."""
    from src.adapters.db.database import async_session_factory
    return async_session_factory()


# ---------------------------------------------------------------------------
# run_scheduled_rescans — triggered by Celery beat every hour
# ---------------------------------------------------------------------------

@celery_app.task(
    name="src.workers.scheduled_tasks.run_scheduled_rescans",
    queue="light",
)
def run_scheduled_rescans() -> dict[str, Any]:
    """Check all investigations with scheduled re-scans due and enqueue them."""
    return _run_async(_async_run_scheduled_rescans())


async def _async_run_scheduled_rescans() -> dict[str, Any]:
    from sqlalchemy import select

    from src.adapters.db.models import InvestigationModel

    triggered = 0
    now = utcnow()

    async with _session_factory() as db:
        stmt = select(InvestigationModel).where(
            InvestigationModel.seed_inputs.has_key("scheduled_rescan")  # type: ignore[attr-defined]
        )
        investigations = (await db.execute(stmt)).scalars().all()

        for inv in investigations:
            schedule = inv.seed_inputs.get("scheduled_rescan", {})
            next_run_str = schedule.get("next_run_at")
            if not next_run_str:
                continue

            next_run = datetime.fromisoformat(next_run_str)
            if next_run > now:
                continue

            from src.workers.tasks.investigation_tasks import run_investigation
            run_investigation.apply_async(
                args=[str(inv.id)],
                kwargs={"profile": schedule.get("scanner_profile", "standard")},
                queue="heavy",
            )

            delta_map = {
                "daily": timedelta(days=1),
                "weekly": timedelta(weeks=1),
                "monthly": timedelta(days=30),
            }
            delta = delta_map.get(schedule.get("interval", "weekly"), timedelta(weeks=1))
            # Add ±10% jitter to prevent thundering herd when many investigations
            # share the same schedule interval.
            next_run = _add_jitter(now + delta, jitter_pct=0.10)
            schedule["next_run_at"] = next_run.isoformat()
            inv.seed_inputs = {**inv.seed_inputs, "scheduled_rescan": schedule}
            triggered += 1

        await db.commit()

    log.info("scheduled_rescans_triggered", count=triggered)
    return {"triggered": triggered, "checked_at": now.isoformat()}


# ---------------------------------------------------------------------------
# detect_scan_anomalies — run after each investigation completes
# ---------------------------------------------------------------------------

@celery_app.task(
    name="src.workers.scheduled_tasks.detect_scan_anomalies",
    queue="light",
    bind=True,
)
def detect_scan_anomalies(self, investigation_id: str) -> dict[str, Any]:
    """Compare latest scan results against historical baseline and flag anomalies."""
    return _run_async(_async_detect_anomalies(investigation_id))


async def _async_detect_anomalies(investigation_id: str) -> dict[str, Any]:
    from sqlalchemy import func, select

    from src.adapters.db.models import ScanResultModel
    from src.config import get_settings

    settings = get_settings()
    threshold = settings.anomaly_result_threshold
    inv_id = uuid.UUID(investigation_id)
    anomalies: list[dict[str, Any]] = []

    async with _session_factory() as db:
        count_stmt = (
            select(ScanResultModel.scanner_name, func.count().label("count"))
            .where(ScanResultModel.investigation_id == inv_id)
            .group_by(ScanResultModel.scanner_name)
        )
        current_counts = {
            row.scanner_name: row.count
            for row in (await db.execute(count_stmt)).all()
        }

        for scanner_name, count in current_counts.items():
            if count > threshold:
                anomalies.append({
                    "scanner": scanner_name,
                    "count": count,
                    "reason": f"Result count {count} exceeds threshold {threshold}",
                })

    if anomalies:
        log.warning(
            "scan_anomalies_detected",
            investigation_id=investigation_id,
            anomalies=anomalies,
        )

    return {"investigation_id": investigation_id, "anomalies": anomalies}


# ---------------------------------------------------------------------------
# reset_monthly_quotas — run on 1st of each month
# ---------------------------------------------------------------------------

@celery_app.task(
    name="src.workers.scheduled_tasks.reset_monthly_quotas",
    queue="light",
)
def reset_monthly_quotas() -> dict[str, Any]:
    """Reset all scanner quota counters at the start of a new billing period."""
    return _run_async(_async_reset_quotas())


async def _async_reset_quotas() -> dict[str, Any]:
    from sqlalchemy import update

    from src.adapters.db.models import ScannerQuotaModel

    now = utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = (period_start + timedelta(days=32)).replace(day=1)

    async with _session_factory() as db:
        await db.execute(
            update(ScannerQuotaModel).values(
                requests_used=0,
                period_start=period_start,
                period_end=period_end,
            )
        )
        await db.commit()

    log.info("scanner_quotas_reset", period_start=period_start.isoformat())
    return {"reset_at": now.isoformat(), "period_start": period_start.isoformat()}


# ---------------------------------------------------------------------------
# purge_celery_results — run daily to prevent Redis bloat
# ---------------------------------------------------------------------------

@celery_app.task(
    name="src.workers.scheduled_tasks.purge_celery_results",
    queue="light",
)
def purge_celery_results(max_age_days: int = 7) -> dict[str, Any]:
    """Delete Celery task result keys from Redis older than `max_age_days`.

    Celery sets result_expires=86400 (24 h) by default, but long-running
    investigations can produce thousands of result keys that accumulate faster
    than the TTL cleans them.  This task does an explicit SCAN + DEL pass to
    ensure the result backend stays lean.
    """
    return _run_async(_async_purge_celery_results(max_age_days))


async def _async_purge_celery_results(max_age_days: int) -> dict[str, Any]:
    import redis.asyncio as aioredis

    from src.config import get_settings

    settings = get_settings()
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    cutoff_seconds = max_age_days * 86400
    deleted = 0

    try:
        # Celery stores results under keys matching "celery-task-meta-*"
        cursor: int = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match="celery-task-meta-*", count=200)
            for key in keys:
                ttl = await redis_client.ttl(key)
                # ttl == -1 means no expiry set (persistent key) — safe to delete
                # ttl == -2 means already gone
                if ttl == -1:
                    await redis_client.delete(key)
                    deleted += 1
            if cursor == 0:
                break
    finally:
        await redis_client.aclose()

    log.info("celery_results_purged", deleted=deleted, max_age_days=max_age_days)
    return {"deleted": deleted, "max_age_days": max_age_days}


# ---------------------------------------------------------------------------
# add_jitter_to_scheduled_rescan — scheduled rescan with jitter
# ---------------------------------------------------------------------------

def _add_jitter(next_run_at: datetime, jitter_pct: float = 0.10) -> datetime:
    """Add ±jitter_pct of the day to a scheduled datetime to prevent thundering herd."""
    import random

    seconds_in_day = 86400
    max_jitter_seconds = int(seconds_in_day * jitter_pct)
    jitter = random.randint(-max_jitter_seconds, max_jitter_seconds)
    return next_run_at + timedelta(seconds=jitter)
