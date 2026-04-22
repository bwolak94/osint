"""Hybrid RAG retriever: dense pgvector cosine + sparse pg_trgm similarity."""

from __future__ import annotations

from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.rag.embedder import BGEEmbedder

log = structlog.get_logger(__name__)


class HybridRetriever:
    """Retrieves the top-k most relevant ``rag_chunks`` for a query.

    Strategy:
    - Dense: cosine similarity against the ``embedding`` (pgvector) column,
      weighted 70 %.
    - Sparse: pg_trgm ``similarity(content, query)`` score, weighted 30 %.

    When Ollama is unavailable the embedder returns a zero vector and the
    combined score degrades to pure sparse / keyword matching — retrieval
    still works, just with lower semantic accuracy.

    When the ``rag_chunks`` table does not yet exist (migration pending) all
    queries return an empty list so the API stays operational.
    """

    def __init__(self, db: AsyncSession, embedder: BGEEmbedder) -> None:
        self._db = db
        self._embedder = embedder

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        sources: Optional[list[str]] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Return up to *k* chunks ranked by combined dense + sparse score."""
        query_embedding = await self._embedder.embed(query)
        use_dense = not self._embedder.is_zero_vector(query_embedding)

        source_filter = "AND source = ANY(:sources)" if sources else ""
        tenant_filter = "(tenant_id IS NULL OR tenant_id = :tenant_id::uuid)"

        if use_dense:
            # Full hybrid: dense 70% + sparse 30%
            sql = text(f"""
                SELECT
                    id,
                    source,
                    source_id,
                    content,
                    metadata,
                    1 - (embedding <=> :embedding::vector)             AS dense_score,
                    similarity(content, :query)                        AS sparse_score,
                    (1 - (embedding <=> :embedding::vector)) * 0.7
                        + similarity(content, :query) * 0.3            AS combined_score
                FROM rag_chunks
                WHERE {tenant_filter}
                {source_filter}
                ORDER BY combined_score DESC
                LIMIT :limit
            """)
        else:
            # Sparse-only fallback when embedding is unavailable
            log.warning("hybrid_retriever.dense_unavailable_fallback_to_keyword")
            sql = text(f"""
                SELECT
                    id,
                    source,
                    source_id,
                    content,
                    metadata,
                    0.0                              AS dense_score,
                    similarity(content, :query)      AS sparse_score,
                    similarity(content, :query)      AS combined_score
                FROM rag_chunks
                WHERE {tenant_filter}
                {source_filter}
                ORDER BY combined_score DESC
                LIMIT :limit
            """)

        params: dict = {
            "embedding": str(query_embedding),
            "query": query,
            "tenant_id": tenant_id,
            "limit": k * 2,  # over-fetch; rerank to final k below
        }
        if sources:
            params["sources"] = sources

        try:
            result = await self._db.execute(sql, params)
            rows = result.fetchall()
        except ProgrammingError as exc:
            # Table or extension missing — log and return empty
            log.warning("hybrid_retriever.table_missing", error=str(exc))
            return []
        except Exception as exc:
            log.error("hybrid_retriever.query_error", error=str(exc))
            return []

        return [
            {
                "id": str(row.id),
                "source": row.source,
                "source_id": row.source_id,
                "content": row.content,
                "metadata": row.metadata,
                "score": float(row.combined_score),
            }
            for row in rows[:k]
        ]

    async def count_by_source(
        self, tenant_id: Optional[str] = None
    ) -> list[dict]:
        """Return chunk counts grouped by source (for the /rag/sources endpoint)."""
        sql = text("""
            SELECT source, COUNT(*) AS chunk_count
            FROM rag_chunks
            WHERE (tenant_id IS NULL OR tenant_id = :tenant_id::uuid)
            GROUP BY source
            ORDER BY source
        """)
        try:
            result = await self._db.execute(sql, {"tenant_id": tenant_id})
            rows = result.fetchall()
            return [{"source": row.source, "chunk_count": int(row.chunk_count)} for row in rows]
        except ProgrammingError as exc:
            log.warning("hybrid_retriever.sources_table_missing", error=str(exc))
            return []
        except Exception as exc:
            log.error("hybrid_retriever.sources_error", error=str(exc))
            return []
