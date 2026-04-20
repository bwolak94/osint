"""Graph analysis tasks — community detection, confidence propagation, attribution.

These tasks operate on the knowledge graph produced by the investigation pipeline.
They are routed to the dedicated ``graph`` queue (separate worker pool) to avoid
starving I/O-bound scanner tasks.

All tasks return compact summary dicts.  Large node/edge payloads are always read
from and written back to the database — they are never passed through the Celery
result backend.
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
    name="src.workers.tasks.community_detection_tasks.detect_communities",
    queue="graph",
    max_retries=1,
    soft_time_limit=120,
)
def detect_communities(self, investigation_id: str, algorithm: str = "louvain") -> dict:
    """Detect entity communities in an investigation's knowledge graph.

    Loads the graph (nodes + edges) from the database, runs the specified
    community-detection algorithm via ``CommunityDetector``, then persists
    the community assignments back as graph node tags / group labels so that
    the frontend can colour-code clusters.

    Supported algorithms (passed through to the adapter):
    - ``"louvain"`` (default) — fast, good modularity.
    - ``"leiden"`` — higher quality, slower.
    - ``"label_propagation"`` — linear time, approximate.

    A ``soft_time_limit`` of 120 s is enforced to protect against pathological
    graphs.  The worker will raise ``SoftTimeLimitExceeded`` and the task will
    not be retried (max_retries=1 is a safety net for transient DB errors only).

    Args:
        investigation_id: Investigation whose graph should be clustered.
        algorithm: Community detection algorithm name (default ``"louvain"``).

    Returns:
        dict with keys: investigation_id, community_count, modularity_score,
        algorithm.
    """

    async def _run() -> dict:
        log.info(
            "Running community detection",
            investigation_id=investigation_id,
            algorithm=algorithm,
        )

        try:
            from src.adapters.community_detector import CommunityDetector  # type: ignore[import]

            detector = CommunityDetector()

            # Load nodes and edges from DB (stubbed — replace with async repo calls).
            nodes: list[dict] = []  # await GraphRepository.get_nodes(investigation_id)
            edges: list[dict] = []  # await GraphRepository.get_edges(investigation_id)

            result = await detector.detect(nodes, edges, algorithm=algorithm)

            # Persist community assignments back to DB (stubbed).
            # await GraphRepository.save_community_labels(
            #     investigation_id, result.communities
            # )

            log.info(
                "Community detection complete",
                investigation_id=investigation_id,
                algorithm=result.algorithm_used,
                communities=len(result.communities),
                modularity=result.modularity_score,
            )

            return {
                "investigation_id": investigation_id,
                "community_count": len(result.communities),
                "modularity_score": float(result.modularity_score),
                "algorithm": result.algorithm_used,
            }

        except Exception as exc:
            log.error(
                "Community detection failed",
                investigation_id=investigation_id,
                algorithm=algorithm,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

    return _run_async(_run())


@shared_task(
    bind=True,
    name="src.workers.tasks.community_detection_tasks.propagate_confidence",
    queue="graph",
    max_retries=1,
)
def propagate_confidence(self, investigation_id: str) -> dict:
    """Propagate confidence scores through an investigation's knowledge graph.

    Loads the weighted directed graph from the DB and runs the
    ``ConfidencePropagator`` adapter, which implements belief propagation:
    high-confidence seed nodes (e.g. directly confirmed IOCs) spread their
    confidence to reachable neighbours, discounted by edge weight.

    Updated scores are written back to the DB so the graph UI can display
    confidence heat-maps.

    Args:
        investigation_id: Investigation whose node confidence should be updated.

    Returns:
        dict with keys: investigation_id, nodes_updated.
    """

    async def _run() -> dict:
        log.info("Propagating confidence scores", investigation_id=investigation_id)

        try:
            from src.adapters.confidence_propagator import ConfidencePropagator  # type: ignore[import]

            propagator = ConfidencePropagator()

            # Load graph from DB (stubbed).
            nodes: list[dict] = []  # await GraphRepository.get_nodes(investigation_id)
            edges: list[dict] = []  # await GraphRepository.get_edges(investigation_id)

            updated_scores: dict = await propagator.propagate(nodes, edges)

            # Persist updated confidence values (stubbed).
            # await GraphRepository.save_node_confidence(investigation_id, updated_scores)

            log.info(
                "Confidence propagation complete",
                investigation_id=investigation_id,
                nodes_updated=len(updated_scores),
            )

            return {
                "investigation_id": investigation_id,
                "nodes_updated": len(updated_scores),
            }

        except Exception as exc:
            log.error(
                "Confidence propagation failed",
                investigation_id=investigation_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

    return _run_async(_run())


@shared_task(
    bind=True,
    name="src.workers.tasks.community_detection_tasks.score_attribution",
    queue="light",
    max_retries=1,
)
def score_attribution(self, investigation_id: str) -> dict:
    """Score investigation entities against the threat-actor attribution library.

    Loads entities and scan results for the investigation and passes them to
    ``AttributionScorer``.  The scorer compares observable TTPs, infrastructure
    patterns, and IOC overlap against a curated threat-actor database and returns
    ranked attribution hypotheses with confidence scores.

    The top-3 actor matches are returned in the summary dict and persisted to
    the DB for display in the investigation UI.

    Args:
        investigation_id: Investigation to score.

    Returns:
        dict with keys: investigation_id, top_actors (list of [actor, confidence]
        pairs, max 3 entries).
    """

    async def _run() -> dict:
        log.info("Scoring threat-actor attribution", investigation_id=investigation_id)

        try:
            from src.adapters.attribution_scorer import AttributionScorer  # type: ignore[import]

            scorer = AttributionScorer()

            # Load entities and scan results from DB (stubbed).
            entities: list[dict] = []      # await EntityRepository.get_all(investigation_id)
            scan_results: list[dict] = []  # await ScanResultRepository.get_all(investigation_id)

            results = scorer.score(entities=entities, scan_results=scan_results)

            # Persist attribution results (stubbed).
            # await AttributionRepository.save(investigation_id, results)

            top_actors = [
                [r.threat_actor, float(r.confidence)]
                for r in results[:3]
            ]

            log.info(
                "Attribution scoring complete",
                investigation_id=investigation_id,
                top_actors=top_actors,
            )

            return {
                "investigation_id": investigation_id,
                "top_actors": top_actors,
            }

        except Exception as exc:
            log.error(
                "Attribution scoring failed",
                investigation_id=investigation_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

    return _run_async(_run())
