"""Knowledge Base API router.

Endpoints:
  POST   /knowledge/ingest       — file upload or URL, enqueues Celery task
  DELETE /knowledge/{doc_id}     — delete all Qdrant chunks for a document
  GET    /knowledge/{doc_id}     — get document metadata (from Qdrant payload)
"""

from __future__ import annotations

import base64
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.knowledge.schemas import IngestRequest, IngestResponse, KnowledgeDocResponse
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _get_celery_task():
    """Lazy import Celery task to keep router testable without a broker."""
    from src.workers.tasks.knowledge_tasks import ingest_knowledge_task  # noqa: PLC0415

    return ingest_knowledge_task


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile | None = File(None),
    url: str | None = None,
    tags: str = "",
) -> IngestResponse:
    """Accept a file upload or URL and enqueue an ingestion Celery task.

    Exactly one of ``file`` or ``url`` must be provided.

    Returns immediately with a job_id for status polling.
    """
    if file is None and url is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either a file upload or a url parameter.",
        )

    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    if file is not None:
        raw_bytes = await file.read()
        content_b64 = base64.b64encode(raw_bytes).decode()
        mime_type = file.content_type or "text/plain"
        source = file.filename or f"upload:{doc_id}"
    else:
        # URL ingestion: content will be fetched inside the Celery worker
        content_b64 = base64.b64encode(url.encode()).decode()  # type: ignore[union-attr]
        mime_type = "text/html"
        source = str(url)

    await log.ainfo(
        "knowledge_ingest_queued",
        doc_id=doc_id,
        job_id=job_id,
        source=source,
        user_id=str(current_user.id),
    )

    ingest_task = _get_celery_task()
    ingest_task.apply_async(
        kwargs={
            "doc_id": doc_id,
            "user_id": str(current_user.id),
            "source": source,
            "content_b64": content_b64,
            "mime_type": mime_type,
            "tags": tag_list,
        },
        task_id=job_id,
    )

    return IngestResponse(job_id=job_id, doc_id=doc_id, status="queued")


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_document(
    doc_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete all Qdrant chunks associated with a document."""
    try:
        from src.adapters.qdrant.client import get_qdrant_client  # noqa: PLC0415

        client = get_qdrant_client()
        await client.delete(
            collection_name="knowledge",
            points_selector={"filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}},
        )
        await log.ainfo("knowledge_deleted", doc_id=doc_id, user_id=str(current_user.id))
    except ImportError:
        await log.awarning("knowledge_delete_no_qdrant", doc_id=doc_id)


@router.get("/{doc_id}", response_model=KnowledgeDocResponse)
async def get_document(
    doc_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> KnowledgeDocResponse:
    """Return metadata for a knowledge document (from Qdrant payload of first chunk)."""
    try:
        from datetime import datetime, timezone  # noqa: PLC0415

        from src.adapters.qdrant.client import get_qdrant_client  # noqa: PLC0415

        client = get_qdrant_client()
        results = await client.scroll(
            collection_name="knowledge",
            scroll_filter={
                "must": [{"key": "doc_id", "match": {"value": doc_id}}]
            },
            limit=1,
            with_payload=True,
        )
        points = results[0] if results else []
        if not points:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        payload = points[0].payload or {}
        # Count all chunks
        all_results = await client.scroll(
            collection_name="knowledge",
            scroll_filter={"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
            limit=10000,
            with_payload=False,
        )
        chunk_count = len(all_results[0]) if all_results else 0

        return KnowledgeDocResponse(
            doc_id=doc_id,
            source=payload.get("source", ""),
            chunk_count=chunk_count,
            tags=payload.get("tags", []),
            created_at=datetime.now(timezone.utc),
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant client not available",
        )
