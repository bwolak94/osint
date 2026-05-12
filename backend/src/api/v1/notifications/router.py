"""In-app notification endpoints — list, mark read, unread count."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_extras_models import NotificationModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["notifications"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str | None
    entity_type: str | None
    entity_id: str | None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedNotificationsResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(m: NotificationModel) -> NotificationResponse:
    return NotificationResponse(
        id=m.id,
        user_id=m.user_id,
        type=m.type,
        title=m.title,
        body=m.body,
        entity_type=m.entity_type,
        entity_id=m.entity_id,
        read=m.read,
        created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedNotificationsResponse)
async def list_notifications(
    current_user: UserDep,
    db: DbDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedNotificationsResponse:
    """List notifications for the current user — unread first, then by creation date desc."""
    from sqlalchemy import func

    base_stmt = select(NotificationModel).where(NotificationModel.user_id == current_user.id)

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Unread first, then newest first
    stmt = (
        base_stmt.order_by(NotificationModel.read.asc(), NotificationModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedNotificationsResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# POST /notifications/{id}/read
# ---------------------------------------------------------------------------


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> NotificationResponse:
    stmt = select(NotificationModel).where(
        NotificationModel.id == notification_id,
        NotificationModel.user_id == current_user.id,
    )
    notification = (await db.execute(stmt)).scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    notification.read = True
    await db.flush()
    await db.refresh(notification)
    return _to_response(notification)


# ---------------------------------------------------------------------------
# POST /notifications/read-all
# ---------------------------------------------------------------------------


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def mark_all_notifications_read(
    current_user: UserDep,
    db: DbDep,
) -> None:
    """Mark all unread notifications for the current user as read."""
    stmt = (
        update(NotificationModel)
        .where(
            NotificationModel.user_id == current_user.id,
            NotificationModel.read.is_(False),
        )
        .values(read=True)
    )
    await db.execute(stmt)
    await db.flush()
    log.info("all_notifications_marked_read", user_id=str(current_user.id))


# ---------------------------------------------------------------------------
# GET /notifications/unread-count
# ---------------------------------------------------------------------------


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: UserDep,
    db: DbDep,
) -> UnreadCountResponse:
    from sqlalchemy import func

    stmt = select(func.count()).where(
        NotificationModel.user_id == current_user.id,
        NotificationModel.read.is_(False),
    )
    count: int = (await db.execute(stmt)).scalar_one()
    return UnreadCountResponse(count=count)
