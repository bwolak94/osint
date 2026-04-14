"""Celery tasks for OSINT scanning.

These are thin wrappers that delegate to the core use cases.
"""

import asyncio
from uuid import UUID

from src.adapters.graph.neo4j_store import Neo4jGraphStore
from src.adapters.osint.scanner import StubOsintScanner
from src.core.use_cases.resolve_identity import ResolveIdentity, ResolveIdentityInput
from src.workers.celery_app import celery_app


def _run_async(coro):  # noqa: ANN001, ANN202
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="osint.run_scan", max_retries=3)
def run_scan(self, identity_id: str, query: str, depth: int = 2) -> dict:  # noqa: ANN001
    """Launch an OSINT scan for a given identity.

    Args:
        identity_id: UUID string of the identity to scan.
        query: The search query.
        depth: How deep to follow links.
    """
    scanner = StubOsintScanner()
    graph = Neo4jGraphStore()

    use_case = ResolveIdentity(scanner=scanner, graph=graph)
    input_data = ResolveIdentityInput(
        identity_id=UUID(identity_id),
        query=query,
        depth=depth,
    )

    result = _run_async(use_case.execute(input_data))
    _run_async(graph.close())
    return result


@celery_app.task(bind=True, name="osint.process_results")
def process_results(self, scan_result: dict) -> dict:  # noqa: ANN001
    """Post-process scan results (enrichment, deduplication, etc.).

    Stub: returns the input as-is.
    """
    # TODO: implement result enrichment and deduplication logic
    return {
        "status": "processed",
        "nodes_count": len(scan_result.get("nodes", [])),
        "raw": scan_result,
    }
