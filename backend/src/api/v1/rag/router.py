"""RAG knowledge base API router.

Endpoints:
  POST /rag/search          — hybrid retrieval (authenticated users)
  GET  /rag/sources         — list sources and chunk counts (authenticated)
  POST /rag/ingest/trigger  — manually trigger nightly ingestion (admin only)
"""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.rag.embedder import BGEEmbedder
from src.adapters.rag.retriever import HybridRetriever
from src.api.v1.auth.dependencies import get_current_user, require_role
from src.config import get_settings
from src.core.domain.entities.types import UserRole
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter(tags=["rag"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Natural-language query")
    k: int = Field(default=5, ge=1, le=50, description="Number of chunks to return")
    sources: Optional[list[str]] = Field(
        default=None,
        description="Filter by source (nvd, owasp-top10, owasp-cheatsheet, cisa-kev)",
    )


class RAGChunkResult(BaseModel):
    id: str
    source: str
    source_id: str
    content: str
    metadata: dict
    score: float


class RAGSearchResponse(BaseModel):
    query: str
    results: list[RAGChunkResult]
    total: int


class RAGSourceInfo(BaseModel):
    source: str
    chunk_count: int


class RAGSourcesResponse(BaseModel):
    sources: list[RAGSourceInfo]


class IngestTriggerResponse(BaseModel):
    task_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_embedder() -> BGEEmbedder:
    settings = get_settings()
    return BGEEmbedder(ollama_host=settings.ollama_host)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/rag/search",
    response_model=RAGSearchResponse,
    summary="Hybrid RAG retrieval",
    description="Search the knowledge base using dense (pgvector) + sparse (pg_trgm) retrieval.",
)
async def rag_search(
    body: RAGSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGSearchResponse:
    """Return the top-k most relevant chunks for the given query.

    Tenant isolation: global chunks (tenant_id IS NULL) are always included.
    Per-user chunks are scoped to the requesting user's ID.
    """
    embedder = _make_embedder()
    retriever = HybridRetriever(db=db, embedder=embedder)

    # Use user ID as tenant boundary (no dedicated tenant_id field on User).
    tenant_id = str(current_user.id)

    results = await retriever.retrieve(
        query=body.query,
        k=body.k,
        sources=body.sources,
        tenant_id=tenant_id,
    )

    log.info(
        "rag.search",
        user_id=str(current_user.id),
        query_len=len(body.query),
        k=body.k,
        returned=len(results),
    )

    return RAGSearchResponse(
        query=body.query,
        results=[RAGChunkResult(**r) for r in results],
        total=len(results),
    )


@router.get(
    "/rag/sources",
    response_model=RAGSourcesResponse,
    summary="List available RAG sources and chunk counts",
)
async def rag_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGSourcesResponse:
    """Return every distinct source in rag_chunks and how many chunks it has."""
    embedder = _make_embedder()
    retriever = HybridRetriever(db=db, embedder=embedder)
    tenant_id = str(current_user.id)

    counts = await retriever.count_by_source(tenant_id=tenant_id)
    return RAGSourcesResponse(
        sources=[RAGSourceInfo(**row) for row in counts]
    )


@router.post(
    "/rag/ingest/trigger",
    response_model=IngestTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger RAG ingestion (admin only)",
)
async def trigger_ingestion(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> IngestTriggerResponse:
    """Enqueue the nightly RAG ingestion task immediately.

    Requires ADMIN role.  The task runs asynchronously in the Celery worker.
    """
    try:
        from src.workers.rag_ingestion import ingest_all_sources

        task = ingest_all_sources.apply_async()
        log.info("rag.ingest_triggered", task_id=task.id, admin_id=str(current_user.id))

        return IngestTriggerResponse(
            task_id=task.id,
            status="queued",
            message="RAG ingestion task enqueued successfully.",
        )
    except Exception as exc:
        log.error("rag.ingest_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue ingestion task: {exc}",
        )
