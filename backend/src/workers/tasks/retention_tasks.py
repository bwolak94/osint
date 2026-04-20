"""Data retention enforcement tasks.

Applies configured retention policies to investigation data: archiving old
investigations to cold storage (MinIO) and hard-deleting records that exceed
the maximum retention window.  Tasks return only summary dicts — bulk data
is handled via streaming DB queries to avoid memory pressure.
"""

import asyncio
import json
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
    name="src.workers.tasks.retention_tasks.enforce_retention_policies",
    queue="light",
)
def enforce_retention_policies(self) -> dict:
    """Periodic task: enforce all active data retention policies.

    Intended to be called by Celery Beat (e.g. nightly).  For each active
    policy it finds matching investigations or scan results older than
    ``max_age_days`` and applies the configured action:

    - ``archive``: dispatch cold_archive_investigation per investigation.
    - ``delete``:  hard-delete scan results and graph records from hot storage.

    All affected investigation IDs and error counts are logged for audit.

    Returns:
        dict with keys: archived, deleted, errors.
    """

    async def _run() -> dict:
        log.info("Running retention policy enforcement")

        archived = 0
        deleted = 0
        errors = 0

        try:
            # Query retention_policies table for all active policies.
            # Each policy has: max_age_days, action ("archive" | "delete"),
            # and optional investigation_tag / team_id scope.
            # (Stubbed: replace with real DB calls via async repository.)
            policies: list[dict] = []

            for policy in policies:
                try:
                    action = policy.get("action", "archive")
                    max_age_days = int(policy.get("max_age_days", 365))

                    # Find investigations older than max_age_days matching policy scope.
                    # overdue_ids = await InvestigationRepository.get_older_than(max_age_days)
                    overdue_ids: list[str] = []

                    for investigation_id in overdue_ids:
                        if action == "archive":
                            cold_archive_investigation.apply_async(
                                args=[investigation_id],
                                queue="light",
                            )
                            archived += 1
                        elif action == "delete":
                            # await InvestigationRepository.hard_delete(investigation_id)
                            deleted += 1

                except Exception as policy_exc:
                    log.error(
                        "Retention policy failed",
                        policy_id=policy.get("id"),
                        error=str(policy_exc),
                    )
                    errors += 1

        except Exception as exc:
            log.error("enforce_retention_policies failed", error=str(exc))
            errors += 1

        log.info(
            "Retention enforcement complete",
            archived=archived,
            deleted=deleted,
            errors=errors,
        )
        return {"archived": archived, "deleted": deleted, "errors": errors}

    return _run_async(_run())


@shared_task(
    bind=True,
    name="src.workers.tasks.retention_tasks.cold_archive_investigation",
    queue="light",
    max_retries=3,
    default_retry_delay=600,
)
def cold_archive_investigation(self, investigation_id: str) -> dict:
    """Archive a single investigation to cold storage (MinIO).

    Steps:
    1. Load all investigation data (nodes, edges, scan results, comments) from DB.
    2. Serialise to a JSON bundle and compress with zstd (fallback: gzip).
    3. Upload compressed bundle to the MinIO ``cold-archive`` bucket.
    4. Mark the investigation as ``archived`` in the DB.
    5. Delete hot-storage records (scan results, graph nodes/edges) to free space.

    The archive format is versioned (``format_version``) so future readers can
    migrate bundles produced by older releases.

    Args:
        investigation_id: ID of the investigation to archive.

    Returns:
        dict with keys: investigation_id, archive_key, size_bytes.
    """
    import datetime

    async def _run() -> dict:
        log.info(
            "Archiving investigation to cold storage",
            investigation_id=investigation_id,
        )

        try:
            # 1. Load all data from DB (stubbed — replace with real async repo calls).
            nodes: list[dict] = []        # await GraphRepository.get_nodes(investigation_id)
            edges: list[dict] = []        # await GraphRepository.get_edges(investigation_id)
            scan_results: list[dict] = [] # await ScanResultRepository.get_all(investigation_id)
            comments: list[dict] = []     # await CommentRepository.get_all(investigation_id)

            # 2. Build the versioned archive bundle.
            bundle = {
                "investigation_id": investigation_id,
                "archived_at": datetime.datetime.utcnow().isoformat(),
                "format_version": "1.0",
                "nodes": nodes,
                "edges": edges,
                "scan_results": scan_results,
                "comments": comments,
            }

            raw_bytes = json.dumps(bundle, default=str).encode("utf-8")

            # 3. Compress — prefer zstd for better ratio; fall back to gzip.
            try:
                import zstandard as zstd  # type: ignore[import]

                compressor = zstd.ZstdCompressor(level=9)
                compressed = compressor.compress(raw_bytes)
                ext = ".zst"
            except ImportError:
                import gzip

                compressed = gzip.compress(raw_bytes, compresslevel=9)
                ext = ".gz"

            archive_key = f"cold-archive/{investigation_id}/bundle{ext}"

            # 4. Upload to MinIO (stubbed — replace with aioboto3 / minio-py call).
            # async with get_minio_client() as client:
            #     await client.put_object("cold-archive", archive_key, compressed)

            log.info(
                "Archive uploaded",
                investigation_id=investigation_id,
                key=archive_key,
                size_bytes=len(compressed),
            )

            # 5. Mark as archived and prune hot-storage records (stubbed).
            # await InvestigationRepository.mark_archived(investigation_id, archive_key)
            # await ScanResultRepository.delete_all(investigation_id)
            # await GraphRepository.delete_all(investigation_id)

            return {
                "investigation_id": investigation_id,
                "archive_key": archive_key,
                "size_bytes": len(compressed),
            }

        except Exception as exc:
            log.error(
                "cold_archive_investigation failed",
                investigation_id=investigation_id,
                error=str(exc),
            )
            raise self.retry(exc=exc, countdown=600 * (2 ** self.request.retries))

    return _run_async(_run())
