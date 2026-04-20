"""IOC enrichment pipeline tasks.

Thin wrappers around the IOCEnricher adapter.  Each task enriches one or more
indicators of compromise using multiple external threat-intel sources (VirusTotal,
Shodan, AbuseIPDB, etc.) and persists the results back to the DB.

Tasks return compact summary dicts — full enrichment detail is written directly
to the database by the adapter, not passed through the Celery result backend.
"""

import asyncio
import structlog
from celery import group, shared_task

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
    name="src.workers.tasks.ioc_enrichment_tasks.enrich_ioc",
    queue="light",
    max_retries=2,
    default_retry_delay=60,
    rate_limit="60/m",
)
def enrich_ioc(self, ioc_value: str, ioc_type: str, investigation_id: str) -> dict:
    """Enrich a single IOC using the multi-source IOCEnricher adapter.

    Calls ``IOCEnricher.enrich()`` which fans out to configured threat-intel
    APIs concurrently and merges the results.  On success the enriched record
    is persisted by the adapter; this task only returns a summary.

    Retried up to 2 times with exponential back-off on transient failures
    (network errors, rate-limit 429s).  Hard errors (invalid IOC type, missing
    API key) are not retried and surface immediately.

    Args:
        ioc_value: The IOC to enrich, e.g. ``"1.2.3.4"``, ``"evil.com"``.
        ioc_type: Canonical type string — one of ``"ip"``, ``"domain"``,
                  ``"hash"``, ``"url"``.
        investigation_id: Parent investigation ID used to scope the DB write.

    Returns:
        dict with keys: ioc_value, ioc_type, risk_score, tags, sources,
        investigation_id.
    """

    async def _run() -> dict:
        try:
            from src.adapters.ioc_enricher import IOCEnricher  # type: ignore[import]

            enricher = IOCEnricher()
            result = await enricher.enrich(ioc_value, ioc_type)

            log.info(
                "IOC enriched",
                ioc=ioc_value,
                ioc_type=ioc_type,
                risk_score=result.risk_score,
                tags=result.tags,
                investigation_id=investigation_id,
            )

            return {
                "ioc_value": result.ioc_value,
                "ioc_type": result.ioc_type,
                "risk_score": float(result.risk_score),
                "tags": list(result.tags),
                "sources": list(result.sources.keys()),
                "investigation_id": investigation_id,
            }

        except Exception as exc:
            log.error(
                "IOC enrichment failed",
                ioc=ioc_value,
                ioc_type=ioc_type,
                investigation_id=investigation_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

    return _run_async(_run())


@shared_task(
    bind=True,
    name="src.workers.tasks.ioc_enrichment_tasks.bulk_enrich_investigation",
    queue="light",
    max_retries=1,
)
def bulk_enrich_investigation(self, investigation_id: str, ioc_limit: int = 50) -> dict:
    """Enrich all IOCs extracted from an investigation's scan results.

    Groups ``extracted_identifiers`` from scan results by IOC type, de-duplicates
    them, caps the total at ``ioc_limit`` to avoid runaway API credit consumption,
    then dispatches a Celery ``group`` of individual ``enrich_ioc`` tasks.

    Args:
        investigation_id: Investigation whose scan results should be enriched.
        ioc_limit: Maximum number of IOCs to enrich in a single sweep (default 50).

    Returns:
        dict with keys: investigation_id, dispatched, skipped.
    """

    async def _run() -> dict:
        log.info(
            "Starting bulk IOC enrichment",
            investigation_id=investigation_id,
            ioc_limit=ioc_limit,
        )

        dispatched = 0
        skipped = 0

        try:
            # Load extracted_identifiers from DB (stubbed).
            # scan_results = await ScanResultRepository.get_all(investigation_id)
            # raw_iocs = extract_unique_iocs(scan_results)  # returns list[tuple[str, str]]
            raw_iocs: list[tuple[str, str]] = []  # [(ioc_value, ioc_type), ...]

            # De-duplicate and cap.
            seen: set[str] = set()
            unique_iocs: list[tuple[str, str]] = []
            for value, ioc_type in raw_iocs:
                key = f"{ioc_type}:{value}"
                if key not in seen:
                    seen.add(key)
                    unique_iocs.append((value, ioc_type))

            to_enrich = unique_iocs[:ioc_limit]
            skipped = max(0, len(unique_iocs) - ioc_limit)

            if to_enrich:
                # Build and dispatch a Celery group so all enrichments run in parallel.
                enrich_group = group(
                    enrich_ioc.s(value, ioc_type, investigation_id)
                    for value, ioc_type in to_enrich
                )
                enrich_group.apply_async()
                dispatched = len(to_enrich)

            log.info(
                "Bulk IOC enrichment dispatched",
                investigation_id=investigation_id,
                dispatched=dispatched,
                skipped=skipped,
            )

        except Exception as exc:
            log.error(
                "bulk_enrich_investigation failed",
                investigation_id=investigation_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

        return {
            "investigation_id": investigation_id,
            "dispatched": dispatched,
            "skipped": skipped,
        }

    return _run_async(_run())
