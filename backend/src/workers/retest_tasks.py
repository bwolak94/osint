"""Celery tasks for pentest finding retest / fix-verification."""

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
# retest_finding
# ---------------------------------------------------------------------------


@celery_app.task(name="pentest.retest_finding", bind=True, queue="pentest_light")
def retest_finding(self, retest_id: str) -> dict[str, Any]:
    """Verify whether a finding has been remediated by re-running the original scanner."""
    return _run_async(_async_retest_finding(self, retest_id))


async def _async_retest_finding(task: Any, retest_id: str) -> dict[str, Any]:
    from sqlalchemy import select

    from src.adapters.db.pentest_extras_models import RetestModel
    from src.adapters.db.pentest_models import PentestFindingModel, PentestScanModel, TargetModel
    from src.adapters.scanners.pentest.ffuf_runner import FfufRunner
    from src.adapters.scanners.pentest.gobuster_runner import GobusterRunner
    from src.adapters.scanners.pentest.httpx_runner import HttpxRunner
    from src.adapters.scanners.pentest.nmap_runner import NmapRunner
    from src.adapters.scanners.pentest.nuclei_runner import NucleiRunner
    from src.adapters.scanners.pentest.sqlmap_runner import SqlmapRunner
    from src.adapters.scanners.pentest.sslyze_runner import SslyzeRunner
    from src.adapters.scanners.pentest.subfinder_runner import SubfinderRunner
    from src.adapters.scanners.pentest.zap_runner import ZapRunner

    runner_registry = {
        "subfinder": SubfinderRunner(),
        "httpx": HttpxRunner(),
        "nmap": NmapRunner(),
        "nuclei": NucleiRunner(),
        "sslyze": SslyzeRunner(),
        "zap": ZapRunner(),
        "ffuf": FfufRunner(),
        "gobuster": GobusterRunner(),
        "sqlmap": SqlmapRunner(),
    }

    session_factory = _make_session_factory()
    async with session_factory() as db:
        # 1. Load RetestModel
        retest_stmt = select(RetestModel).where(RetestModel.id == uuid.UUID(retest_id))
        retest = (await db.execute(retest_stmt)).scalar_one_or_none()
        if retest is None:
            await log.aerror("retest_not_found", retest_id=retest_id)
            return {"error": "retest not found"}

        retest.status = "running"
        await db.commit()

        # 2. Load original finding
        finding_stmt = select(PentestFindingModel).where(
            PentestFindingModel.id == retest.finding_id
        )
        finding = (await db.execute(finding_stmt)).scalar_one_or_none()
        if finding is None:
            retest.status = "fail"
            retest.completed_at = _utcnow()
            retest.notes = "Original finding record not found."
            await db.commit()
            return {"error": "finding not found"}

        # 3. Load scan and target to resolve the target address
        target_value: str | None = None

        if finding.scan_id is not None:
            scan_stmt = select(PentestScanModel).where(PentestScanModel.id == finding.scan_id)
            scan = (await db.execute(scan_stmt)).scalar_one_or_none()

            if scan is not None:
                tgt_stmt = select(TargetModel).where(TargetModel.id == scan.target_id)
                target = (await db.execute(tgt_stmt)).scalar_one_or_none()
                if target is not None:
                    target_value = target.value

        # Fallback: extract from finding.target JSONB blob
        if target_value is None and finding.target:
            target_blob = finding.target
            target_value = (
                target_blob.get("url")
                or target_blob.get("hostname")
                or target_blob.get("ip")
            )

        if not target_value:
            retest.status = "fail"
            retest.completed_at = _utcnow()
            retest.notes = "Could not resolve target address for retest."
            await db.commit()
            return {"error": "target address not resolvable"}

        # 4. Instantiate the correct runner based on finding.tool
        tool_name = finding.tool or "nuclei"
        runner = runner_registry.get(tool_name)
        if runner is None:
            # Fallback to nuclei if the original tool is unrecognised
            runner = runner_registry["nuclei"]
            await log.awarn(
                "retest_unknown_tool_fallback",
                original_tool=tool_name,
                retest_id=retest_id,
            )

        try:
            # 5. Run the scanner against the target
            result = await runner.run(target_value)

            vulnerability_still_present = len(result.findings) > 0

            if vulnerability_still_present:
                # 6a. Vulnerability still found — retest FAIL
                retest.status = "fail"
                retest.notes = (
                    f"Vulnerability still present after retest. "
                    f"Tool '{tool_name}' returned {len(result.findings)} finding(s)."
                )
                # Restore finding status to confirmed if it was marked remediated
                if finding.status == "remediated":
                    finding.status = "confirmed"
            else:
                # 6b. Not found — retest PASS, keep finding as remediated
                retest.status = "pass"
                retest.notes = (
                    f"Vulnerability not detected in retest. "
                    f"Tool '{tool_name}' returned 0 findings."
                )
                # If finding was confirmed, advance to remediated
                if finding.status == "confirmed":
                    finding.status = "remediated"

            retest.completed_at = _utcnow()
            await db.commit()

            await log.ainfo(
                "retest_complete",
                retest_id=retest_id,
                finding_id=str(finding.id),
                status=retest.status,
                tool=tool_name,
                target=target_value,
            )

            return {
                "retest_id": retest_id,
                "finding_id": str(finding.id),
                "status": retest.status,
                "tool": tool_name,
                "findings_count": len(result.findings),
            }

        except Exception as exc:
            retest.status = "fail"
            retest.completed_at = _utcnow()
            retest.notes = f"Retest runner raised an exception: {exc}"
            await db.commit()
            await log.aerror(
                "retest_runner_failed",
                retest_id=retest_id,
                error=str(exc),
            )
            return {"error": str(exc), "retest_id": retest_id, "status": "fail"}
