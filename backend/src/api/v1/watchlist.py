"""Watch list / continuous monitoring endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class WatchListItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    input_value: str = Field(..., min_length=1, max_length=1000)
    input_type: str = Field(..., pattern="^(email|phone|username|nip|url|ip_address|domain)$")
    scanners: list[str] = []
    schedule_cron: str = "0 */6 * * *"
    notify_on_change: bool = True
    notification_channels: list[str] = []


class WatchListItemResponse(BaseModel):
    id: str
    name: str
    description: str
    input_value: str
    input_type: str
    scanners: list[str]
    schedule_cron: str
    is_active: bool
    notify_on_change: bool
    notification_channels: list[str]
    last_scan_at: str | None
    scan_count: int
    change_count: int
    last_change_at: str | None
    created_at: str


class WatchListResponse(BaseModel):
    items: list[WatchListItemResponse]
    total: int


@router.get("/watchlist", response_model=WatchListResponse)
async def list_watchlist(
    current_user: Any = Depends(get_current_user),
) -> WatchListResponse:
    """List all watch list items for the current user."""
    return WatchListResponse(items=[], total=0)


@router.post("/watchlist", response_model=WatchListItemResponse, status_code=201)
async def create_watchlist_item(
    body: WatchListItemCreate,
    current_user: Any = Depends(get_current_user),
) -> WatchListItemResponse:
    """Create a new watch list item for continuous monitoring."""
    now = datetime.now(timezone.utc).isoformat()
    return WatchListItemResponse(
        id=str(secrets.token_hex(16)),
        name=body.name,
        description=body.description,
        input_value=body.input_value,
        input_type=body.input_type,
        scanners=body.scanners,
        schedule_cron=body.schedule_cron,
        is_active=True,
        notify_on_change=body.notify_on_change,
        notification_channels=body.notification_channels,
        last_scan_at=None,
        scan_count=0,
        change_count=0,
        last_change_at=None,
        created_at=now,
    )


@router.patch("/watchlist/{item_id}")
async def update_watchlist_item(
    item_id: str,
    body: dict[str, Any],
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Update a watch list item."""
    log.info("Watch list item updated", item_id=item_id)
    return {"status": "updated", "id": item_id}


@router.delete("/watchlist/{item_id}")
async def delete_watchlist_item(
    item_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a watch list item."""
    log.info("Watch list item deleted", item_id=item_id)
    return {"status": "deleted", "id": item_id}


@router.post("/watchlist/{item_id}/trigger")
async def trigger_watchlist_scan(
    item_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Manually trigger a scan for a watch list item."""
    log.info("Watch list scan triggered", item_id=item_id)
    return {"status": "triggered", "id": item_id}
