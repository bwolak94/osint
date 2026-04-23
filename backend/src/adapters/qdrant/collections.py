"""Qdrant collection management — creation, deletion, health-check.

Collection schema (Phase 1):
  - dense vector:  1536 dims (OpenAI text-embedding-3-small), Cosine distance
  - sparse vector: SPLADE++ via FastEmbed (prithivida/Splade_PP_en_v1)

Payload schema per chunk:
  { doc_id, chunk_index, source, date, tags, user_id, mime_type }
"""

from __future__ import annotations

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseVectorParams,
    VectorParams,
)

log = structlog.get_logger(__name__)

KNOWLEDGE_COLLECTION = "knowledge"
NEWS_COLLECTION = "news"          # Phase 2: news article storage
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DENSE_DIM = 1536                  # openai/text-embedding-3-small (knowledge collection)
NEWS_DENSE_DIM = 384              # BAAI/bge-small-en-v1.5 via FastEmbed (news collection)


class QdrantCollectionManager:
    """Handles collection lifecycle operations.

    Args:
        client: AsyncQdrantClient instance (injected for testability).
    """

    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def ensure_knowledge_collection(self) -> None:
        """Create the knowledge collection if it does not exist.

        Uses upsert semantics — safe to call on every application startup.
        """
        exists = await self._collection_exists(KNOWLEDGE_COLLECTION)
        if exists:
            log.info("qdrant_collection_exists", collection=KNOWLEDGE_COLLECTION)
            return

        await self._client.create_collection(
            collection_name=KNOWLEDGE_COLLECTION,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=DENSE_DIM,
                    distance=Distance.COSINE,
                    on_disk=False,  # keep HNSW index in RAM for < 3ms p99
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams()
            },
        )
        log.info("qdrant_collection_created", collection=KNOWLEDGE_COLLECTION)

    async def ensure_news_collection(self) -> None:
        """Create the news collection if it does not exist.

        Payload schema per article:
          { article_id, source_domain, published_at, credibility_score,
            action_relevance_score, tags, user_id }
        """
        exists = await self._collection_exists(NEWS_COLLECTION)
        if exists:
            log.info("qdrant_collection_exists", collection=NEWS_COLLECTION)
            return

        await self._client.create_collection(
            collection_name=NEWS_COLLECTION,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=NEWS_DENSE_DIM,  # 384-dim BAAI/bge-small-en-v1.5 via FastEmbed
                    distance=Distance.COSINE,
                    on_disk=False,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams()
            },
        )
        log.info("qdrant_collection_created", collection=NEWS_COLLECTION)

        # Create payload index for 'tags' field to make tag filtering fast
        # (avoids full collection scan when filtering by tag)
        try:
            await self._client.create_payload_index(
                collection_name=NEWS_COLLECTION,
                field_name="tags",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            log.info("qdrant_payload_index_created", collection=NEWS_COLLECTION, field="tags")
        except Exception as exc:
            log.warning("qdrant_payload_index_error", collection=NEWS_COLLECTION, field="tags", error=str(exc))

    async def delete_knowledge_collection(self) -> None:
        """Delete the knowledge collection (used in tests / data wipes)."""
        await self._client.delete_collection(collection_name=KNOWLEDGE_COLLECTION)
        log.info("qdrant_collection_deleted", collection=KNOWLEDGE_COLLECTION)

    async def collection_info(self) -> dict[str, object]:
        """Return basic collection metadata (vectors count, status)."""
        info = await self._client.get_collection(KNOWLEDGE_COLLECTION)
        return {
            "name": KNOWLEDGE_COLLECTION,
            "vectors_count": info.vectors_count,
            "status": str(info.status),
        }

    async def _collection_exists(self, name: str) -> bool:
        collections = await self._client.get_collections()
        return any(c.name == name for c in collections.collections)
