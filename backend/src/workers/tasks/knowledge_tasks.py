"""Celery tasks for Knowledge Base ingestion.

Task: knowledge.ingest (queue: light)
  - Decodes base64 content
  - For URL mime_type: fetches content from URL (if source looks like a URL)
  - Calls ingestion.ingest_document()
  - Emits progress events via Redis pub/sub
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_PROGRESS_CHANNEL = "knowledge:ingest:{}:events"
_TTL = 3600


def _get_redis_sync() -> Any:
    """Synchronous Redis client for Celery worker context."""
    from redis import Redis as SyncRedis  # noqa: PLC0415

    from src.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    return SyncRedis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(
    name="knowledge.ingest",
    queue="light",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def ingest_knowledge_task(
    self: Any,
    *,
    doc_id: str,
    user_id: str,
    source: str,
    content_b64: str,
    mime_type: str,
    tags: list[str],
) -> dict[str, Any]:
    """Parse, chunk, and upsert a document to Qdrant.

    Args:
        doc_id:      Pre-generated document UUID.
        user_id:     Owner's user ID.
        source:      Human-readable source (filename or URL).
        content_b64: Base64-encoded raw content.
        mime_type:   MIME type string.
        tags:        User-supplied tags.

    Returns:
        IngestionResult dict with doc_id, chunks_processed, source.
    """
    redis = _get_redis_sync()
    channel = _PROGRESS_CHANNEL.format(doc_id)

    def _publish(event: dict[str, Any]) -> None:
        try:
            redis.publish(channel, json.dumps(event))
        except Exception:
            pass

    try:
        _publish({"type": "ingest_start", "doc_id": doc_id})

        async def _run() -> dict[str, Any]:
            from src.adapters.knowledge.ingestion import MimeType, ingest_document  # noqa: PLC0415
            from src.adapters.qdrant.client import get_qdrant_client  # noqa: PLC0415

            # Try to wire real Qdrant client
            qdrant_client = None
            try:
                qdrant_client = get_qdrant_client()
            except Exception as exc:
                log.warning("knowledge_qdrant_unavailable", error=str(exc))

            # Try to wire real MinIO client
            minio_client = None
            try:
                from src.config import get_settings  # noqa: PLC0415
                settings = get_settings()
                if getattr(settings, "minio_endpoint", None):
                    from minio import Minio  # noqa: PLC0415
                    minio_client = Minio(
                        settings.minio_endpoint,
                        access_key=settings.minio_access_key,
                        secret_key=settings.minio_secret_key,
                        secure=getattr(settings, "minio_secure", False),
                    )
            except Exception as exc:
                log.warning("knowledge_minio_unavailable", error=str(exc))

            raw_content: bytes | str
            decoded = base64.b64decode(content_b64)

            if mime_type == "text/html" and source.startswith(("http://", "https://")):
                from src.adapters.knowledge.parsers.url import parse_url  # noqa: PLC0415

                url = decoded.decode("utf-8", errors="replace")
                raw_content = await parse_url(url)
                effective_mime: MimeType = "text/plain"
            else:
                raw_content = decoded
                effective_mime = mime_type  # type: ignore[assignment]

            # Publish chunk progress before heavy work begins
            _publish({"type": "ingest_chunking", "doc_id": doc_id})

            result = await ingest_document(
                content=raw_content,
                source=source,
                user_id=user_id,
                mime_type=effective_mime,
                tags=tags,
                qdrant_client=qdrant_client,
                minio_client=minio_client,
            )

            # Emit per-chunk progress events when multiple chunks were produced
            chunks_processed: int = result["chunks_processed"]
            if chunks_processed > 1:
                for chunk_idx in range(chunks_processed):
                    _publish(
                        {
                            "type": "ingest_chunk_progress",
                            "doc_id": doc_id,
                            "chunk_index": chunk_idx,
                            "total_chunks": chunks_processed,
                        }
                    )

            return dict(result)

        result = asyncio.run(_run())
        _publish({"type": "ingest_done", "doc_id": doc_id, "chunks": result["chunks_processed"]})
        return result

    except Exception as exc:
        log.error("knowledge_ingest_error", doc_id=doc_id, error=str(exc))
        _publish({"type": "ingest_error", "doc_id": doc_id, "error": str(exc)})
        raise self.retry(exc=exc)
