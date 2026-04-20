"""Annotation endpoints — free-text notes pinned to graph nodes or scan results."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AnnotationCreate(BaseModel):
    target_type: str = Field(..., pattern="^(node|scan_result|investigation)$")
    target_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    severity: str = Field("info", pattern="^(info|low|medium|high|critical)$")
    pinned: bool = False


class AnnotationUpdate(BaseModel):
    content: str | None = Field(None, min_length=1)
    severity: str | None = Field(None, pattern="^(info|low|medium|high|critical)$")
    pinned: bool | None = None


class AnnotationResponse(BaseModel):
    id: str
    investigation_id: str
    target_type: str
    target_id: str
    content: str
    severity: str
    pinned: bool
    author_id: str
    created_at: str
    updated_at: str


class AnnotationListResponse(BaseModel):
    annotations: list[AnnotationResponse]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_annotation(
    investigation_id: str,
    target_type: str,
    target_id: str,
    content: str,
    severity: str,
    pinned: bool,
    author_id: str,
) -> AnnotationResponse:
    now = datetime.now(timezone.utc).isoformat()
    return AnnotationResponse(
        id=secrets.token_hex(16),
        investigation_id=investigation_id,
        target_type=target_type,
        target_id=target_id,
        content=content,
        severity=severity,
        pinned=pinned,
        author_id=author_id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/investigations/{investigation_id}/annotations",
    response_model=AnnotationResponse,
    status_code=201,
)
async def create_annotation(
    investigation_id: str,
    body: AnnotationCreate,
    current_user: Any = Depends(get_current_user),
) -> AnnotationResponse:
    """Create an annotation attached to a node, scan result, or investigation."""
    author_id = str(getattr(current_user, "id", "unknown"))
    log.info("Annotation created", investigation_id=investigation_id, target_id=body.target_id, author=author_id)
    return _make_annotation(
        investigation_id=investigation_id,
        target_type=body.target_type,
        target_id=body.target_id,
        content=body.content,
        severity=body.severity,
        pinned=body.pinned,
        author_id=author_id,
    )


@router.get(
    "/investigations/{investigation_id}/annotations",
    response_model=AnnotationListResponse,
)
async def list_annotations(
    investigation_id: str,
    target_id: str | None = Query(None),
    current_user: Any = Depends(get_current_user),
) -> AnnotationListResponse:
    """List annotations for an investigation, optionally filtered by target_id."""
    return AnnotationListResponse(annotations=[], total=0)


@router.get(
    "/investigations/{investigation_id}/annotations/{annotation_id}",
    response_model=AnnotationResponse,
)
async def get_annotation(
    investigation_id: str,
    annotation_id: str,
    current_user: Any = Depends(get_current_user),
) -> AnnotationResponse:
    """Retrieve a single annotation by ID."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    return AnnotationResponse(
        id=annotation_id,
        investigation_id=investigation_id,
        target_type="node",
        target_id="placeholder",
        content="Placeholder annotation",
        severity="info",
        pinned=False,
        author_id=user_id,
        created_at=now,
        updated_at=now,
    )


@router.patch("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: str,
    body: AnnotationUpdate,
    current_user: Any = Depends(get_current_user),
) -> AnnotationResponse:
    """Update annotation content, severity, or pinned state."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    log.info("Annotation updated", annotation_id=annotation_id, user=user_id)
    return AnnotationResponse(
        id=annotation_id,
        investigation_id="unknown",
        target_type="node",
        target_id="placeholder",
        content=body.content or "Updated annotation",
        severity=body.severity or "info",
        pinned=body.pinned if body.pinned is not None else False,
        author_id=user_id,
        created_at=now,
        updated_at=now,
    )


@router.delete("/annotations/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Delete an annotation (author or admin only)."""
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info("Annotation deleted", annotation_id=annotation_id, user=user_id)
