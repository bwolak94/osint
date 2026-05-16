"""Celery tasks for investigation pipeline orchestration (Saga pattern)."""

import asyncio
import structlog
from uuid import UUID, uuid4

from celery import chain, chord, group

from src.workers.celery_app import celery_app
from src.workers.tasks.scanner_tasks import (
    holehe_scan_task,
    maigret_scan_task,
    playwright_scan_task,
    vat_scan_task,
)
from src.workers.tasks.graph_tasks import resolve_entities_task, build_graph_task

log = structlog.get_logger()

# Maps input types to their task dispatchers
_TASK_MAP = {
    "email": lambda sid, val, inv: holehe_scan_task.s(sid, val, inv),
    "username": lambda sid, val, inv: maigret_scan_task.s(sid, val, inv),
    "nip": lambda sid, val, inv: group(
        vat_scan_task.s(sid, val, inv),
        playwright_scan_task.s(sid, val, "nip", "playwright_krs", inv),
        playwright_scan_task.s(uuid4().hex, val, "nip", "playwright_ceidg", inv),
    ),
}


@celery_app.task(bind=True, name="investigations.run", max_retries=1)
def run_investigation_task(self, investigation_id: str) -> dict:
    """Orchestrate the full scanning pipeline for an investigation.

    Pipeline (Saga pattern):
    1. Load investigation and its seed inputs
    2. Dispatch scanners for each seed (parallel per seed, sequential stages)
    3. After all scans complete → entity resolution
    4. After resolution → build knowledge graph
    5. Mark investigation as completed

    Each step is a Celery task, enabling retry and checkpointing.
    """
    log.info("Investigation pipeline started", investigation_id=investigation_id)

    try:
        # Build scan tasks from seed inputs
        scan_tasks = _build_scan_tasks(investigation_id)

        if not scan_tasks:
            log.warning("No scan tasks generated", investigation_id=investigation_id)
            return {"investigation_id": investigation_id, "status": "no_seeds"}

        # Pipeline: all scans in parallel → entity resolution → graph build
        pipeline = chord(
            group(scan_tasks),
            chain(
                resolve_entities_task.si(investigation_id),
                build_graph_task.si(investigation_id),
                _complete_investigation_task.si(investigation_id),
            ),
        )
        pipeline.apply_async()

        return {"investigation_id": investigation_id, "status": "dispatched", "task_count": len(scan_tasks)}

    except Exception as exc:
        log.error("Investigation pipeline failed", investigation_id=investigation_id, error=str(exc))
        return {"investigation_id": investigation_id, "status": "failed", "error": str(exc)}


def _build_scan_tasks(investigation_id: str) -> list:
    """Load seed inputs and create corresponding scan tasks.

    TODO: implement real DB loading via a synchronous SQLAlchemy session.
    Until then this returns an empty list and the Saga orchestrator will
    report "no_seeds" — use ``run_osint_investigation`` (the other task)
    which is the live code path dispatched from the API router.
    """
    log.warning(
        "_build_scan_tasks not implemented — Saga orchestrator has no seeds",
        investigation_id=investigation_id,
    )
    return []


@celery_app.task(name="investigations.complete")
def _complete_investigation_task(graph_result: dict, investigation_id: str) -> dict:
    """Mark the investigation as completed after all pipeline steps finish."""
    log.info("Investigation pipeline completed", investigation_id=investigation_id)
    return {"investigation_id": investigation_id, "status": "completed"}


@celery_app.task(
    bind=True,
    name="src.workers.tasks.investigation_tasks.run_osint_investigation",
    max_retries=0,
    queue="light",
)
def run_osint_investigation(
    self,
    investigation_id: str,
    seed_inputs_data: list[dict],
    enabled_scanners: list[str] | None = None,
) -> dict:
    """Run the full OSINT scan pipeline for an investigation via Celery.

    Accepts serialised seed inputs (list of {"value": ..., "input_type": ...})
    so the task is fully self-contained and can be retried independently of the
    HTTP request context.
    """
    from src.api.v1.investigations.router import _run_scans_background
    from src.core.domain.entities.types import ScanInputType, SeedInput

    seeds = [
        SeedInput(value=d["value"], input_type=ScanInputType(d["input_type"]))
        for d in seed_inputs_data
    ]

    try:
        asyncio.run(_run_scans_background(investigation_id, seeds, enabled_scanners))
    except Exception as exc:
        log.error("OSINT investigation task failed", investigation_id=investigation_id, error=str(exc))
        # Attempt to mark the investigation as failed so completed_at is always set.
        # Log cleanup failures explicitly — swallowing them silently hides issues.
        try:
            from src.api.v1.investigations.router import _mark_investigation_failed
            asyncio.run(_mark_investigation_failed(investigation_id))
        except Exception as cleanup_exc:
            log.error(
                "OSINT investigation cleanup failed",
                investigation_id=investigation_id,
                cleanup_error=str(cleanup_exc),
            )
        raise

    return {"investigation_id": investigation_id, "status": "completed"}


@celery_app.task(
    bind=True,
    name="src.workers.tasks.investigation_tasks.run_single_target_scan",
    max_retries=1,
    queue="light",
)
def run_single_target_scan(
    self,
    target: str,
    scanners: list[str] | None = None,
    user_id: str | None = None,
    bulk_id: str | None = None,
    label: str | None = None,
) -> dict:
    """Run OSINT scans on a single target (for bulk scan API)."""
    from src.adapters.scanners.registry import get_default_registry
    from src.core.domain.entities.types import ScanInputType

    log.info("Single target scan started", target=target, bulk_id=bulk_id)
    registry = get_default_registry()

    # Auto-detect input type
    if "@" in target:
        input_type = ScanInputType.EMAIL
    elif target.startswith("http://") or target.startswith("https://"):
        input_type = ScanInputType.URL
    elif target.replace(".", "").replace(":", "").isdigit():
        input_type = ScanInputType.IP_ADDRESS
    else:
        input_type = ScanInputType.DOMAIN

    results: list[dict] = []

    async def _run() -> None:
        candidates = registry.get_for_input_type(input_type)
        if scanners:
            candidates = [s for s in candidates if s.scanner_name in scanners]
        for scanner in candidates[:20]:  # cap at 20 scanners per target
            try:
                result = await scanner.scan(target, input_type)
                results.append({"scanner": scanner.scanner_name, "result": result})
            except Exception as exc:
                log.debug("Single scan failed", scanner=scanner.scanner_name, error=str(exc))

    asyncio.run(_run())
    return {
        "bulk_id": bulk_id,
        "target": target,
        "label": label,
        "input_type": input_type.value,
        "results": results,
        "total_scanners": len(results),
    }
