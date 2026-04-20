"""Elasticsearch adapter for full-text search across investigations and scan results."""

from typing import Any
from uuid import UUID

import structlog
from src.config import get_settings

log = structlog.get_logger()


class ElasticsearchStore:
    """Adapter for indexing and searching OSINT data in Elasticsearch."""

    def __init__(self) -> None:
        self._client = None
        self._settings = get_settings()

    async def _get_client(self):
        """Lazy-initialize the Elasticsearch async client."""
        if self._client is None:
            try:
                from elasticsearch import AsyncElasticsearch

                self._client = AsyncElasticsearch(
                    self._settings.elasticsearch_url,
                    basic_auth=(
                        self._settings.elasticsearch_username,
                        self._settings.elasticsearch_password,
                    )
                    if self._settings.elasticsearch_username
                    else None,
                )
            except ImportError:
                log.warning("elasticsearch package not installed, search features disabled")
                return None
        return self._client

    def _index_name(self, entity_type: str) -> str:
        return f"{self._settings.elasticsearch_index_prefix}_{entity_type}"

    async def index_investigation(self, investigation_id: UUID, data: dict[str, Any]) -> bool:
        """Index an investigation document."""
        client = await self._get_client()
        if not client:
            return False
        try:
            await client.index(
                index=self._index_name("investigations"),
                id=str(investigation_id),
                document=data,
            )
            return True
        except Exception as e:
            log.error("Failed to index investigation", id=str(investigation_id), error=str(e))
            return False

    async def index_scan_result(self, result_id: UUID, data: dict[str, Any]) -> bool:
        """Index a scan result document."""
        client = await self._get_client()
        if not client:
            return False
        try:
            await client.index(
                index=self._index_name("scan_results"),
                id=str(result_id),
                document=data,
            )
            return True
        except Exception as e:
            log.error("Failed to index scan result", id=str(result_id), error=str(e))
            return False

    async def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        owner_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Full-text search across indexed entities."""
        client = await self._get_client()
        if not client:
            return {"total": 0, "results": [], "page": page, "page_size": page_size}

        indices = (
            ",".join(self._index_name(t) for t in entity_types)
            if entity_types
            else f"{self._settings.elasticsearch_index_prefix}_*"
        )

        must_clauses: list[dict] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "title^3",
                        "description^2",
                        "tags",
                        "input_value",
                        "raw_data.*",
                    ],
                    "fuzziness": "AUTO",
                }
            }
        ]
        if owner_id:
            must_clauses.append({"term": {"owner_id": str(owner_id)}})

        body = {
            "query": {"bool": {"must": must_clauses}},
            "from": (page - 1) * page_size,
            "size": page_size,
            "highlight": {"fields": {"title": {}, "description": {}, "raw_data.*": {}}},
        }

        try:
            resp = await client.search(index=indices, body=body)
            hits = resp.get("hits", {})
            return {
                "total": hits.get("total", {}).get("value", 0),
                "results": [
                    {
                        "id": hit["_id"],
                        "index": hit["_index"],
                        "score": hit["_score"],
                        "source": hit["_source"],
                        "highlights": hit.get("highlight", {}),
                    }
                    for hit in hits.get("hits", [])
                ],
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            log.error("Search failed", query=query, error=str(e))
            return {
                "total": 0,
                "results": [],
                "page": page,
                "page_size": page_size,
                "error": str(e),
            }

    async def delete_investigation(self, investigation_id: UUID) -> bool:
        """Remove an investigation from the index."""
        client = await self._get_client()
        if not client:
            return False
        try:
            await client.delete(
                index=self._index_name("investigations"),
                id=str(investigation_id),
                ignore=[404],
            )
            return True
        except Exception as e:
            log.error(
                "Failed to delete investigation from index",
                id=str(investigation_id),
                error=str(e),
            )
            return False

    async def ensure_indices(self) -> None:
        """Create indices with mappings if they don't exist."""
        client = await self._get_client()
        if not client:
            return

        investigation_mapping = {
            "mappings": {
                "properties": {
                    "title": {"type": "text", "analyzer": "standard"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "tags": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "owner_id": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
        }

        scan_result_mapping = {
            "mappings": {
                "properties": {
                    "investigation_id": {"type": "keyword"},
                    "scanner_name": {"type": "keyword"},
                    "input_value": {"type": "text"},
                    "status": {"type": "keyword"},
                    "raw_data": {"type": "object", "enabled": True},
                    "extracted_identifiers": {"type": "keyword"},
                    "created_at": {"type": "date"},
                }
            }
        }

        for idx, mapping in [
            (self._index_name("investigations"), investigation_mapping),
            (self._index_name("scan_results"), scan_result_mapping),
        ]:
            try:
                if not await client.indices.exists(index=idx):
                    await client.indices.create(index=idx, body=mapping)
                    log.info("Created index", index=idx)
            except Exception as e:
                log.error("Failed to create index", index=idx, error=str(e))

    async def close(self) -> None:
        """Close the Elasticsearch client."""
        if self._client:
            await self._client.close()
            self._client = None
