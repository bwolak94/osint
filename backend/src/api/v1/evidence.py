"""Evidence tagging endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class EvidenceTagCreate(BaseModel):
    investigation_id: str
    scan_result_id: str | None = None
    node_id: str | None = None
    tag_name: str = Field(..., min_length=1, max_length=100)
    tag_color: str = "#6366f1"
    notes: str = ""
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class EvidenceTagResponse(BaseModel):
    id: str
    investigation_id: str
    scan_result_id: str | None
    node_id: str | None
    tag_name: str
    tag_color: str
    notes: str
    confidence: float
    created_by: str
    created_at: str


class EvidenceListResponse(BaseModel):
    tags: list[EvidenceTagResponse]
    total: int


@router.get("/investigations/{investigation_id}/evidence", response_model=EvidenceListResponse)
async def list_evidence(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> EvidenceListResponse:
    return EvidenceListResponse(tags=[], total=0)


@router.post(
    "/investigations/{investigation_id}/evidence",
    response_model=EvidenceTagResponse,
    status_code=201,
)
async def create_evidence_tag(
    investigation_id: str,
    body: EvidenceTagCreate,
    current_user: Any = Depends(get_current_user),
) -> EvidenceTagResponse:
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    return EvidenceTagResponse(
        id=secrets.token_hex(16),
        investigation_id=investigation_id,
        scan_result_id=body.scan_result_id,
        node_id=body.node_id,
        tag_name=body.tag_name,
        tag_color=body.tag_color,
        notes=body.notes,
        confidence=body.confidence,
        created_by=user_id,
        created_at=now,
    )


@router.delete("/investigations/{investigation_id}/evidence/{tag_id}")
async def delete_evidence_tag(
    investigation_id: str,
    tag_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "deleted", "id": tag_id}
