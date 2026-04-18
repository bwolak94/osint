"""Full-text search API endpoint powered by Elasticsearch."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.search.elasticsearch_store import ElasticsearchStore
from src.core.domain.entities.user import User

router = APIRouter()

_es_store: ElasticsearchStore | None = None


def get_es_store() -> ElasticsearchStore:
    global _es_store
    if _es_store is None:
        _es_store = ElasticsearchStore()
    return _es_store


class SearchResponse(BaseModel):
    total: int
    results: list[dict]
    page: int
    page_size: int
    error: str | None = None


@router.get("/search/fulltext", response_model=SearchResponse)
async def fulltext_search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    entity_types: Optional[str] = Query(None, description="Comma-separated: investigations,scan_results"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    es: ElasticsearchStore = Depends(get_es_store),
) -> SearchResponse:
    """Search across all indexed OSINT data."""
    types = entity_types.split(",") if entity_types else None
    result = await es.search(
        query=q,
        entity_types=types,
        owner_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return SearchResponse(**result)
