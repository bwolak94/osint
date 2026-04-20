"""Scheduled investigation re-scan tasks — run saved investigations on a cron schedule.

These are thin wrappers around the investigation pipeline. They do NOT contain
business logic — only Celery orchestration concerns (retry, logging, serialization).
Tasks return only summary dicts, never raw investigation data (that stays in PostgreSQL).
"""

import asyncio
import structlog
from celery import shared_task

log = structlog.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="src.workers.tasks.scheduled_scan_tasks.run_scheduled_rescan",
    queue="light",
    max_retries=2,
    default_retry_delay=300,
)
def run_scheduled_rescan(self, investigation_id: str, profile_id: str | None = None) -> dict:
    """Re-run all scans for an investigation using its saved seed inputs.

    Loads the investigation from the database, applies an optional scan profile,
    then dispatches individual scanner tasks for each seed input identical to the
    original run_investigation_task pipeline.  The activity log is updated so
    analysts can distinguish scheduled re-scans from manual ones.

    Args:
        investigation_id: ID of the investigation to re-scan.
        profile_id: Optional scan-profile ID whose scanner allow-list / rate
                    overrides should be applied.

    Returns:
        dict with keys: investigation_id, profile_id, status, scan_count.
    """

    async def _run() -> dict:
        log.info(
            "Starting scheduled rescan",
            investigation_id=investigation_id,
            profile_id=profile_id,
        )

        try:
            # 1. Load investigation from DB — validates existence before dispatching.
            #    (Stubbed: in production import and call an async repository method.)
            # investigation = await InvestigationRepository.get(investigation_id)

            # 2. Load scan profile if provided.
            # profile = await ScanProfileRepository.get(profile_id) if profile_id else None

            # 3. Re-use the existing investigation pipeline task so scanner
            #    orchestration logic is not duplicated here.
            from src.workers.tasks.investigation_tasks import run_investigation_task

            run_investigation_task.apply_async(
                args=[investigation_id],
                kwargs={},
                queue="light",
            )

            # 4. Record activity log entry (stubbed).
            log.info(
                "Scheduled rescan dispatched",
                investigation_id=investigation_id,
                profile_id=profile_id,
            )

            return {
                "investigation_id": investigation_id,
                "profile_id": profile_id,
                "status": "dispatched",
                "scan_count": 1,
            }

        except Exception as exc:
            log.error(
                "Scheduled rescan failed",
                investigation_id=investigation_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=300 * (2 ** self.request.retries))

    return _run_async(_run())


@shared_task(
    bind=True,
    name="src.workers.tasks.scheduled_scan_tasks.process_scheduled_rescans",
    queue="light",
)
def process_scheduled_rescans(self) -> dict:
    """Periodic task: find investigations due for a scheduled re-scan and dispatch them.

    Intended to be called by Celery Beat on a short interval (e.g. every minute).
    Queries investigations where ``next_scan_at <= now()`` and a schedule is
    configured, then fires run_scheduled_rescan for each overdue investigation.

    Returns:
        dict with keys: checked, dispatched.
    """

    async def _run() -> dict:
        log.info("Checking for due scheduled rescans")

        checked = 0
        dispatched = 0

        try:
            # Query DB for overdue scheduled investigations.
            # Example (stubbed):
            #   overdue = await InvestigationRepository.get_overdue_scheduled()
            overdue: list[dict] = []

            checked = len(overdue)
            for inv in overdue:
                run_scheduled_rescan.apply_async(
                    args=[inv["investigation_id"]],
                    kwargs={"profile_id": inv.get("scan_profile_id")},
                    queue="light",
                )
                dispatched += 1

            log.info(
                "Scheduled rescan sweep complete",
                checked=checked,
                dispatched=dispatched,
            )

        except Exception as exc:
            log.error("process_scheduled_rescans failed", error=str(exc))
            # Do not retry a periodic sweep — it will run again on the next tick.

        return {"checked": checked, "dispatched": dispatched}

    return _run_async(_run())
