"""Celery tasks for graph operations and entity resolution."""

import asyncio
import structlog
from uuid import UUID

from src.workers.celery_app import celery_app

log = structlog.get_logger()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="graph.resolve_entities", queue="graph")
def resolve_entities_task(self, investigation_id: str) -> dict:
    """Run entity resolution on all scan results for an investigation."""
    try:
        from src.adapters.entity_resolution.resolver import SimpleEntityResolver

        resolver = SimpleEntityResolver()
        clusters = _run_async(resolver.resolve(UUID(investigation_id)))

        log.info("Entity resolution completed", investigation_id=investigation_id, clusters=len(clusters))
        return {"investigation_id": investigation_id, "cluster_count": len(clusters)}

    except Exception as exc:
        log.error("Entity resolution failed", investigation_id=investigation_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="graph.build_graph", queue="graph")
def build_graph_task(self, investigation_id: str) -> dict:
    """Build the Neo4j knowledge graph from resolved entities."""
    log.info("Graph build started", investigation_id=investigation_id)
    # Placeholder — will be implemented with Neo4j adapter
    return {"investigation_id": investigation_id, "status": "completed"}
