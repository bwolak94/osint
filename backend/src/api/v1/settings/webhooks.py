"""Webhook management endpoints."""

import secrets
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.webhook_models import WebhookModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class CreateWebhookRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2000)
    events: list[str] = Field(default_factory=lambda: ["scan_complete", "investigation_complete"])


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    secret: str
    is_active: bool
    created_at: str


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WebhookResponse]:
    stmt = select(WebhookModel).where(WebhookModel.user_id == current_user.id)
    result = await db.execute(stmt)
    return [
        WebhookResponse(
            id=str(w.id), url=w.url, events=list(w.events),
            secret=w.secret[:8] + "..." if w.secret else "",
            is_active=w.is_active, created_at=w.created_at.isoformat(),
        )
        for w in result.scalars().all()
    ]


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: CreateWebhookRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    secret = secrets.token_hex(32)
    webhook = WebhookModel(
        id=uuid4(), user_id=current_user.id,
        url=body.url, events=body.events, secret=secret,
    )
    db.add(webhook)
    await db.flush()
    return WebhookResponse(
        id=str(webhook.id), url=webhook.url, events=list(webhook.events),
        secret=secret,  # Show full secret only on creation
        is_active=True, created_at=webhook.created_at.isoformat(),
    )


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    webhook = await db.get(WebhookModel, webhook_id)
    if not webhook or webhook.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(webhook)
    await db.flush()
