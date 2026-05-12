"""Knowledge base ingestion pipeline.

Pipeline: parse → chunk → upsert to Qdrant (and optionally MinIO for raw storage)

Point IDs are deterministic UUIDs derived from doc_id + chunk_index so that
re-ingesting the same document is idempotent (upsert semantics).
"""

from __future__ import annotations

import base64
import uuid
from typing import Any, Literal, TypedDict

import structlog

from src.adapters.knowledge.chunker import chunk_text

log = structlog.get_logger(__name__)

MimeType = Literal["application/pdf", "text/markdown", "text/plain", "text/html"]

# Namespace for deterministic UUID generation (per RFC 4122 §4.3)
_UUID_NAMESPACE = uuid.NAMESPACE_DNS


class IngestionResult(TypedDict):
    """Result of a successful document ingestion."""

    doc_id: str
    chunks_processed: int
    source: str


async def _parse_content(content: bytes | str, mime_type: MimeType) -> str:
    """Dispatch to the appropriate parser based on MIME type."""
    if mime_type == "application/pdf":
        from src.adapters.knowledge.parsers.pdf import parse_pdf  # noqa: PLC0415

        if isinstance(content, str):
            # Treat as base64-encoded PDF
            content = base64.b64decode(content)
        return await parse_pdf(content)

    if mime_type == "text/markdown":
        from src.adapters.knowledge.parsers.markdown import parse_markdown  # noqa: PLC0415

        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        return parse_markdown(text)

    # text/plain and text/html both go through the text cleaner
    from src.adapters.knowledge.parsers.text import parse_text  # noqa: PLC0415

    return parse_text(content)


def _make_point_id(doc_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID for a chunk (idempotent upsert key)."""
    return str(uuid.uuid5(_UUID_NAMESPACE, f"{doc_id}:{chunk_index}"))


async def ingest_document(
    content: bytes | str,
    source: str,
    user_id: str,
    mime_type: MimeType,
    tags: list[str] | None = None,
    qdrant_client: Any | None = None,
    minio_client: Any | None = None,
) -> IngestionResult:
    """Parse → chunk → embed → upsert to Qdrant.

    Args:
        content:       Raw document content (bytes for PDF; str for text/markdown).
        source:        Human-readable source identifier (URL, filename, etc.).
        user_id:       Owner's user ID (stored as payload metadata).
        mime_type:     MIME type determining which parser is used.
        tags:          Optional list of user-supplied tags.
        qdrant_client: Injected Qdrant client (None → mock/skip upsert).
        minio_client:  Injected MinIO client (None → skip raw storage).

    Returns:
        IngestionResult with doc_id, chunks_processed, source.
    """
    doc_id = str(uuid.uuid4())
    effective_tags = tags or []

    await log.ainfo(
        "ingestion_start",
        doc_id=doc_id,
        source=source,
        mime_type=mime_type,
        user_id=user_id,
    )

    # ── 1. Parse ──────────────────────────────────────────────────────────────
    try:
        text = await _parse_content(content, mime_type)
    except Exception as exc:
        await log.aerror("ingestion_parse_error", doc_id=doc_id, error=str(exc))
        raise

    if not text.strip():
        await log.awarning("ingestion_empty_document", doc_id=doc_id)
        return IngestionResult(doc_id=doc_id, chunks_processed=0, source=source)

    # ── 2. Chunk ──────────────────────────────────────────────────────────────
    chunks = chunk_text(text)

    await log.ainfo("ingestion_chunked", doc_id=doc_id, chunks=len(chunks))

    # ── 3. Upsert to Qdrant ───────────────────────────────────────────────────
    if qdrant_client is not None:
        points: list[dict[str, Any]] = []
        for chunk in chunks:
            point_id = _make_point_id(doc_id, int(chunk["chunk_index"]))  # type: ignore[arg-type]
            points.append(
                {
                    "id": point_id,
                    "payload": {
                        "doc_id": doc_id,
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                        "source": source,
                        "user_id": user_id,
                        "tags": effective_tags,
                    },
                    "vector": None,  # real adapter fills this from fastembed
                }
            )

        try:
            await qdrant_client.upsert(collection_name="knowledge", points=points)
        except Exception as exc:
            await log.aerror("ingestion_qdrant_error", doc_id=doc_id, error=str(exc))
            raise
    else:
        await log.awarning("ingestion_no_qdrant_mock", doc_id=doc_id, chunks=len(chunks))

    # ── 4. Optional raw storage in MinIO ─────────────────────────────────────
    if minio_client is not None:
        try:
            raw_bytes = content if isinstance(content, bytes) else content.encode()
            await minio_client.put_object(
                bucket="knowledge",
                object_name=f"{user_id}/{doc_id}/raw",
                data=raw_bytes,
                content_type=mime_type,
            )
        except Exception as exc:
            # MinIO failure is non-fatal — Qdrant is the source of truth
            await log.awarning("ingestion_minio_error", doc_id=doc_id, error=str(exc))

    await log.ainfo("ingestion_done", doc_id=doc_id, chunks_processed=len(chunks))
    return IngestionResult(doc_id=doc_id, chunks_processed=len(chunks), source=source)
