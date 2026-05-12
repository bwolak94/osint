"""Webhook management endpoints with retry + dead-letter queue."""

import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated
from uuid import UUID, uuid4

import structlog
from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.webhook_models import WebhookModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter()

_DEAD_LETTER_KEY = "webhook:dead_letter"
_MAX_DL_SIZE = 1000      # cap dead-letter list length
_DELIVERY_TIMEOUT = 10   # seconds per attempt
_MAX_RETRIES = 3


async def deliver_webhook(
    url: str,
    secret: str,
    payload: dict,
    max_retries: int = _MAX_RETRIES,
) -> bool:
    """Deliver a webhook payload with exponential-backoff retry.

    On all retries exhausted, push to Redis dead-letter list so admins can
    inspect and replay failed deliveries.

    Returns True on success, False on permanent failure.
    """
    import asyncio
    import random

    import httpx

    from src.config import get_settings

    settings = get_settings()
    body = json.dumps(payload, default=str).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-OSINT-Signature": f"sha256={sig}",
        "X-OSINT-Event": payload.get("event", "unknown"),
    }

    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 400:
                    log.info("webhook_delivered", url=url, attempt=attempt + 1)
                    return True
                last_error = f"HTTP {resp.status_code}"
        except Exception as exc:
            last_error = str(exc)

        if attempt < max_retries:
            delay = min(2 ** attempt + random.uniform(0, 1), 30)
            log.warning("webhook_retry", url=url, attempt=attempt + 1, delay=round(delay, 1), error=last_error)
            await asyncio.sleep(delay)

    # All retries exhausted — push to dead-letter queue
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        dead_letter_entry = json.dumps({
            "url": url,
            "payload": payload,
            "last_error": last_error,
            "failed_at": time.time(),
            "retries": max_retries,
        })
        await redis_client.lpush(_DEAD_LETTER_KEY, dead_letter_entry)
        await redis_client.ltrim(_DEAD_LETTER_KEY, 0, _MAX_DL_SIZE - 1)
        await redis_client.aclose()
    except Exception:
        pass

    log.error("webhook_delivery_failed", url=url, retries=max_retries, error=last_error)
    return False


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


@router.delete("/webhooks/{webhook_id}", status_code=204, response_model=None)
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


@router.get("/webhooks/dead-letter", response_model=list[dict])
async def get_dead_letter_queue(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
) -> list[dict]:
    """Return recent failed webhook deliveries from the dead-letter queue.

    Entries include the original URL, payload, error message, and failure
    timestamp so operators can investigate and replay failed deliveries.
    """
    import redis.asyncio as aioredis

    from src.config import get_settings

    settings = get_settings()
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        entries = await redis_client.lrange(_DEAD_LETTER_KEY, 0, limit - 1)
        await redis_client.aclose()
        return [json.loads(e) for e in entries]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}") from exc
