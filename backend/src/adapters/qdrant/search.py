"""Qdrant hybrid search — dense + sparse (SPLADE++) with RRF fusion.

Implements the DocumentRetriever protocol so it can be injected into
the Searcher agent with zero coupling to the Qdrant SDK.

Search pipeline:
  1. Encode query → dense vector (OpenAI text-embedding-3-small)
  2. Encode query → sparse vector (SPLADE++ via FastEmbed)
  3. Prefetch top-20 from each index separately
  4. Fuse results with Reciprocal Rank Fusion (RRF)
  5. Return top-K results as RetrievedDoc TypedDicts

Phase 1: Dense encoder calls OpenAI API.
         Sparse encoder calls local FastEmbed (SPLADE++ prithivida/Splade_PP_en_v1).
"""

from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from src.adapters.hub.state import RetrievedDoc
from src.adapters.qdrant.collections import (
    DENSE_VECTOR_NAME,
    KNOWLEDGE_COLLECTION,
    SPARSE_VECTOR_NAME,
)

log = structlog.get_logger(__name__)

_PREFETCH_LIMIT = 20


class DenseEncoder(Any):  # type: ignore[misc]
    """Protocol for dense vector encoding (OpenAI or local model)."""

    async def encode(self, text: str) -> list[float]: ...


class SparseEncoder(Any):  # type: ignore[misc]
    """Protocol for sparse vector encoding (SPLADE++)."""

    async def encode_sparse(self, text: str) -> dict[str, Any]: ...


class QdrantHybridSearcher:
    """Hybrid dense + sparse semantic search over the knowledge collection.

    Satisfies the DocumentRetriever protocol expected by SearcherAgent.

    Args:
        client:         Async Qdrant client.
        dense_encoder:  Async callable(text) → list[float].
        sparse_encoder: Async callable(text) → {"indices": [...], "values": [...]}.
        user_id:        Filters results to this user's documents only.
    """

    def __init__(
        self,
        client: AsyncQdrantClient,
        dense_encoder: Any,
        sparse_encoder: Any,
        user_id: str,
    ) -> None:
        self._client = client
        self._dense_encoder = dense_encoder
        self._sparse_encoder = sparse_encoder
        self._user_id = user_id

    async def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedDoc]:
        """Run hybrid search and return top-K scored documents.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.

        Returns:
            List of RetrievedDoc dicts ordered by RRF score (descending).
        """
        await log.ainfo(
            "qdrant_hybrid_search",
            query_length=len(query),
            top_k=top_k,
            user_id=self._user_id,
        )

        # Encode in parallel for lower latency
        dense_vector, sparse_vector = await self._encode_query(query)

        user_filter = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=self._user_id))]
        )

        # ── Hybrid search via Qdrant prefetch + RRF fusion ──────────────────
        results = await self._client.query_points(
            collection_name=KNOWLEDGE_COLLECTION,
            prefetch=[
                {
                    "query": dense_vector,
                    "using": DENSE_VECTOR_NAME,
                    "limit": _PREFETCH_LIMIT,
                    "filter": user_filter,
                },
                {
                    "query": {"indices": sparse_vector["indices"], "values": sparse_vector["values"]},
                    "using": SPARSE_VECTOR_NAME,
                    "limit": _PREFETCH_LIMIT,
                    "filter": user_filter,
                },
            ],
            query={"fusion": "rrf"},
            limit=top_k,
            with_payload=True,
        )

        docs: list[RetrievedDoc] = []
        for point in results.points:
            payload = point.payload or {}
            docs.append(
                RetrievedDoc(
                    doc_id=str(payload.get("doc_id", "")),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    text=str(payload.get("text", "")),
                    source=str(payload.get("source", "")),
                    score=float(point.score),
                    tags=list(payload.get("tags", [])),
                )
            )

        await log.ainfo("qdrant_search_done", results=len(docs))
        return docs

    async def _encode_query(
        self, query: str
    ) -> tuple[list[float], dict[str, Any]]:
        """Encode query to dense + sparse vectors concurrently."""
        import asyncio

        dense_task = asyncio.create_task(self._dense_encoder.encode(query))
        sparse_task = asyncio.create_task(self._sparse_encoder.encode_sparse(query))

        dense_vec, sparse_vec = await asyncio.gather(dense_task, sparse_task)
        return dense_vec, sparse_vec
