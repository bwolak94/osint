"""Saved search alerts endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class SavedSearchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    query: str = Field(..., min_length=1)
    filters: dict = {}
    alert_enabled: bool = False
    alert_frequency: str = Field("daily", pattern="^(hourly|daily|weekly)$")


class SavedSearchResponse(BaseModel):
    id: str
    name: str
    query: str
    filters: dict
    alert_enabled: bool
    alert_frequency: str
    last_alert_at: str | None
    result_count: int
    created_at: str


class SavedSearchListResponse(BaseModel):
    searches: list[SavedSearchResponse]
    total: int


@router.get("/saved-searches", response_model=SavedSearchListResponse)
async def list_saved_searches(
    current_user: Any = Depends(get_current_user),
) -> SavedSearchListResponse:
    return SavedSearchListResponse(searches=[], total=0)


@router.post("/saved-searches", response_model=SavedSearchResponse, status_code=201)
async def create_saved_search(
    body: SavedSearchCreate,
    current_user: Any = Depends(get_current_user),
) -> SavedSearchResponse:
    now = datetime.now(timezone.utc).isoformat()
    return SavedSearchResponse(
        id=secrets.token_hex(16),
        name=body.name,
        query=body.query,
        filters=body.filters,
        alert_enabled=body.alert_enabled,
        alert_frequency=body.alert_frequency,
        last_alert_at=None,
        result_count=0,
        created_at=now,
    )


@router.delete("/saved-searches/{search_id}")
async def delete_saved_search(
    search_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "deleted", "id": search_id}


@router.post("/saved-searches/{search_id}/run")
async def run_saved_search(
    search_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    return {"status": "executed", "results": [], "count": 0}
