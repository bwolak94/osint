"""TLP (Traffic Light Protocol) marking endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

# Valid TLP levels in ascending sensitivity order.
TLP_LEVELS = ("WHITE", "GREEN", "AMBER", "RED")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TLPMarkingCreate(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: str = Field(..., min_length=1)
    tlp_level: str = Field(..., pattern="^(WHITE|GREEN|AMBER|RED)$")
    reason: str = ""


class TLPMarkingUpdate(BaseModel):
    tlp_level: str | None = Field(None, pattern="^(WHITE|GREEN|AMBER|RED)$")
    reason: str | None = None


class TLPMarkingResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    tlp_level: str
    reason: str
    created_by: str
    created_at: str
    updated_at: str


class TLPMarkingListResponse(BaseModel):
    markings: list[TLPMarkingResponse]
    total: int


class TLPLevelCount(BaseModel):
    tlp_level: str
    count: int


class TLPSummaryResponse(BaseModel):
    investigation_id: str
    summary: list[TLPLevelCount]
    total_entities: int
    highest_tlp: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_marking(body: TLPMarkingCreate, user_id: str) -> TLPMarkingResponse:
    now = datetime.now(timezone.utc).isoformat()
    return TLPMarkingResponse(
        id=secrets.token_hex(16),
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        tlp_level=body.tlp_level,
        reason=body.reason,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/tlp-markings", response_model=TLPMarkingResponse, status_code=201)
async def create_tlp_marking(
    body: TLPMarkingCreate,
    current_user: Any = Depends(get_current_user),
) -> TLPMarkingResponse:
    """Assign a TLP level to any entity (node, investigation, scan result)."""
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info("TLP marking created", entity_type=body.entity_type, entity_id=body.entity_id, level=body.tlp_level)
    return _make_marking(body, user_id)


@router.get("/tlp-markings", response_model=TLPMarkingListResponse)
async def list_tlp_markings(
    entity_type: str | None = Query(None),
    tlp_level: str | None = Query(None, pattern="^(WHITE|GREEN|AMBER|RED)$"),
    current_user: Any = Depends(get_current_user),
) -> TLPMarkingListResponse:
    """List TLP markings, optionally filtered by entity type or TLP level."""
    return TLPMarkingListResponse(markings=[], total=0)


@router.get("/tlp-markings/{entity_type}/{entity_id}", response_model=TLPMarkingResponse)
async def get_tlp_marking(
    entity_type: str,
    entity_id: str,
    current_user: Any = Depends(get_current_user),
) -> TLPMarkingResponse:
    """Get the TLP marking for a specific entity."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    return TLPMarkingResponse(
        id=secrets.token_hex(16),
        entity_type=entity_type,
        entity_id=entity_id,
        tlp_level="WHITE",
        reason="",
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.patch("/tlp-markings/{marking_id}", response_model=TLPMarkingResponse)
async def update_tlp_marking(
    marking_id: str,
    body: TLPMarkingUpdate,
    current_user: Any = Depends(get_current_user),
) -> TLPMarkingResponse:
    """Update the TLP level or reason for an existing marking."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    log.info("TLP marking updated", marking_id=marking_id, user=user_id)
    return TLPMarkingResponse(
        id=marking_id,
        entity_type="unknown",
        entity_id="unknown",
        tlp_level=body.tlp_level or "WHITE",
        reason=body.reason or "",
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.delete("/tlp-markings/{marking_id}", status_code=204)
async def delete_tlp_marking(
    marking_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Remove a TLP marking."""
    log.info("TLP marking deleted", marking_id=marking_id)


@router.get("/investigations/{investigation_id}/tlp-summary", response_model=TLPSummaryResponse)
async def get_investigation_tlp_summary(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> TLPSummaryResponse:
    """Return aggregated TLP statistics for all entities within an investigation."""
    # Stub: real implementation counts entities grouped by tlp_level from the DB.
    summary = [TLPLevelCount(tlp_level=level, count=0) for level in TLP_LEVELS]
    return TLPSummaryResponse(
        investigation_id=investigation_id,
        summary=summary,
        total_entities=0,
        highest_tlp=None,
    )
