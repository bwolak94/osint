"""OSINT enrichment consumer — processes pentest.finding.confirmed events from Redis.

When a pentest confirms a CVE or technology on a target, this consumer updates
the corresponding OSINT entity's properties in the database with:
  - confirmed_cves: list[str]
  - pentest_severity: str
  - last_pentest_at: str (ISO timestamp)
  - pentest_engagement_id: str

Triggered by: POST /api/v1/scans/{id}/to-osint which publishes to osint:enrich channel.
Also exposes a Celery task (osint.enrich_from_pentest) callable directly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _enrich_neo4j_nodes(event: dict[str, Any]) -> int:
    """Update Neo4j graph nodes matching the pentest target with enrichment data.

    Returns the count of nodes updated.
    """
    from neo4j import AsyncGraphDatabase

    from src.config import get_settings

    settings = get_settings()

    target: dict[str, Any] = event.get("target") or {}
    ip: str | None = target.get("ip") or None
    hostname: str | None = target.get("hostname") or None

    if not ip and not hostname:
        await log.awarning(
            "osint_enrichment_skipped_no_target",
            scan_id=event.get("scan_id"),
            reason="event.target has neither ip nor hostname",
        )
        return 0

    confirmed_cves: list[str] = event.get("cve_ids") or []
    severity: str = event.get("severity") or "unknown"
    last_pentest_at: str = event.get("ts") or ""
    engagement_id: str = event.get("engagement_id") or ""

    enrichment_patch = {
        "confirmed_cves": confirmed_cves,
        "pentest_severity": severity,
        "last_pentest_at": last_pentest_at,
        "pentest_engagement_id": engagement_id,
    }

    # Build label candidates to match against Neo4j nodes
    label_candidates: list[str] = []
    if ip:
        label_candidates.append(ip.strip().lower())
    if hostname:
        label_candidates.append(hostname.strip().lower())

    # Node types that can be enriched with pentest data
    enrichable_types = ["ip", "domain", "subdomain", "url", "service"]

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=30.0,
        max_transaction_retry_time=30.0,
    )
    updated = 0
    try:
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (n)
                WHERE n.label_normalized IN $labels
                  AND n.node_type IN $types
                SET n.properties = apoc.map.merge(
                    coalesce(n.properties, {}),
                    $patch
                )
                RETURN count(n) AS updated
                """,
                labels=label_candidates,
                types=enrichable_types,
                patch=enrichment_patch,
            )
            record = await result.single()
            if record:
                updated = record["updated"]
    except Exception as exc:  # pragma: no cover
        await log.awarning(
            "osint_enrichment_neo4j_failed",
            scan_id=event.get("scan_id"),
            labels=label_candidates,
            error=str(exc),
        )
    finally:
        await driver.close()

    return updated


@celery_app.task(
    bind=True,
    name="osint.enrich_from_pentest",
    queue="light",
    max_retries=3,
    default_retry_delay=60,
)
def enrich_from_pentest(self, event: dict[str, Any]) -> dict[str, Any]:
    """Process a pentest.finding.confirmed event and update matching OSINT nodes.

    Accepts the raw event dict published to the ``osint:enrich`` Redis channel.
    Never crashes — logs warnings on any unexpected error.
    """
    scan_id = event.get("scan_id", "unknown")
    log.info(
        "osint_enrichment_task_started",
        scan_id=scan_id,
        event_type=event.get("event_type"),
    )
    try:
        updated = _run_async(_enrich_neo4j_nodes(event))
        log.info(
            "osint_enrichment_task_completed",
            scan_id=scan_id,
            nodes_updated=updated,
        )
        return {"scan_id": scan_id, "nodes_updated": updated, "status": "ok"}
    except Exception as exc:
        log.warning(
            "osint_enrichment_task_failed",
            scan_id=scan_id,
            error=str(exc),
        )
        # Retry up to max_retries with exponential back-off; never propagate hard
        try:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            log.warning(
                "osint_enrichment_max_retries_exceeded",
                scan_id=scan_id,
                error=str(exc),
            )
            return {"scan_id": scan_id, "nodes_updated": 0, "status": "max_retries_exceeded"}
