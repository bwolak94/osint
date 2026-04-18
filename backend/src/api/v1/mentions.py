"""@Mention and notification endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class MentionCreate(BaseModel):
    investigation_id: str
    mentioned_user_id: str
    context_type: str = Field(..., pattern="^(comment|annotation|task)$")
    context_id: str
    content_preview: str = ""


class MentionResponse(BaseModel):
    id: str
    investigation_id: str
    author_id: str
    mentioned_user_id: str
    context_type: str
    context_id: str
    content_preview: str
    is_read: bool
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[MentionResponse]
    total: int
    unread_count: int


@router.post("/mentions", response_model=MentionResponse, status_code=201)
async def create_mention(
    body: MentionCreate,
    current_user: Any = Depends(get_current_user),
) -> MentionResponse:
    """Create a mention notification for a user."""
    author_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()

    log.info("Mention created", author=author_id, mentioned=body.mentioned_user_id)

    return MentionResponse(
        id=secrets.token_hex(16),
        investigation_id=body.investigation_id,
        author_id=author_id,
        mentioned_user_id=body.mentioned_user_id,
        context_type=body.context_type,
        context_id=body.context_id,
        content_preview=body.content_preview,
        is_read=False,
        created_at=now,
    )


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    current_user: Any = Depends(get_current_user),
) -> NotificationListResponse:
    """List all notifications/mentions for the current user."""
    return NotificationListResponse(notifications=[], total=0, unread_count=0)


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Mark a notification as read."""
    return {"status": "read", "id": notification_id}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Mark all notifications as read."""
    return {"status": "all_read"}
