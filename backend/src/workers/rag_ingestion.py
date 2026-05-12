"""Celery tasks for nightly RAG knowledge base ingestion."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from within a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _upsert_documents(docs: list, source_name: str) -> int:
    """Embed documents and upsert them into rag_chunks. Returns count of upserted rows."""
    if not docs:
        return 0

    from src.adapters.db.database import async_session_factory
    from src.adapters.rag.embedder import BGEEmbedder
    from src.config import get_settings
    from sqlalchemy import text

    settings = get_settings()
    embedder = BGEEmbedder(ollama_host=settings.ollama_host)

    texts = [doc.content for doc in docs]
    embeddings = await embedder.embed_batch(texts)

    upserted = 0
    async with async_session_factory() as session:
        for doc, embedding in zip(docs, embeddings):
            try:
                stmt = text("""
                    INSERT INTO rag_chunks
                        (id, source, source_id, tenant_id, content, metadata, embedding, ingested_at)
                    VALUES
                        (gen_random_uuid(), :source, :source_id, :tenant_id, :content,
                         :metadata::jsonb, :embedding::vector, now())
                    ON CONFLICT (source, source_id)
                    DO UPDATE SET
                        content      = EXCLUDED.content,
                        metadata     = EXCLUDED.metadata,
                        embedding    = EXCLUDED.embedding,
                        ingested_at  = now()
                """)

                import json

                await session.execute(stmt, {
                    "source": doc.source,
                    "source_id": doc.source_id,
                    "tenant_id": None,  # global chunks
                    "content": doc.content,
                    "metadata": json.dumps(doc.metadata),
                    "embedding": str(embedding),
                })
                upserted += 1
            except Exception as exc:
                log.warning(
                    "rag_ingestion.upsert_row_error",
                    source=doc.source,
                    source_id=doc.source_id,
                    error=str(exc),
                )

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            log.error("rag_ingestion.commit_error", source=source_name, error=str(exc))
            return 0

    log.info("rag_ingestion.upsert_complete", source=source_name, count=upserted)
    return upserted


async def _run_all_ingestors() -> dict[str, int]:
    """Instantiate and run every ingestor, upserting results into rag_chunks."""
    from src.adapters.rag.ingestion.nvd_ingestor import NVDIngestor
    from src.adapters.rag.ingestion.cisa_kev_ingestor import CISAKEVIngestor
    from src.adapters.rag.ingestion.owasp_ingestor import (
        OWASPTop10Ingestor,
        OWASPCheatSheetIngestor,
    )

    ingestors = [
        NVDIngestor(),
        CISAKEVIngestor(),
        OWASPTop10Ingestor(),
        OWASPCheatSheetIngestor(),
    ]

    results: dict[str, int] = {}

    for ingestor in ingestors:
        name = ingestor.__class__.__name__
        log.info("rag_ingestion.ingestor_start", ingestor=name)
        try:
            docs = await ingestor.fetch()
            # Filter docs the ingestor wants to skip
            docs = [d for d in docs if not ingestor.should_skip(d)]
            count = await _upsert_documents(docs, name)
            results[name] = count
            log.info("rag_ingestion.ingestor_done", ingestor=name, count=count)
        except Exception as exc:
            log.error("rag_ingestion.ingestor_error", ingestor=name, error=str(exc))
            results[name] = 0

    return results


@celery_app.task(
    name="rag.ingest_all_sources",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def ingest_all_sources(self) -> dict:  # type: ignore[override]
    """Nightly ingestion of all RAG knowledge sources.

    Scheduled at 02:00 UTC via Celery beat.  Can also be triggered manually
    via the ``POST /api/v1/rag/ingest/trigger`` admin endpoint.
    """
    log.info("rag_ingestion.task_start")

    try:
        results = _run_async(_run_all_ingestors())
    except Exception as exc:
        log.error("rag_ingestion.task_error", error=str(exc))
        raise self.retry(exc=exc)

    total = sum(results.values())
    log.info("rag_ingestion.task_complete", total=total, breakdown=results)
    return {"total_chunks_updated": total, "breakdown": results}
