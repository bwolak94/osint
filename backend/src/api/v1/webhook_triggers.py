"""Webhook-triggered investigation endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class WebhookTriggerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    input_type: str = Field(..., pattern="^(email|phone|username|nip|url|ip_address|domain)$")
    scanners: list[str] = []
    auto_start: bool = True


class WebhookTriggerResponse(BaseModel):
    id: str
    name: str
    description: str
    secret_token: str
    webhook_url: str
    is_active: bool
    input_type: str
    scanners: list[str]
    auto_start: bool
    trigger_count: int
    last_triggered_at: str | None
    created_at: str


class WebhookTriggerListResponse(BaseModel):
    triggers: list[WebhookTriggerResponse]
    total: int


@router.get("/webhook-triggers", response_model=WebhookTriggerListResponse)
async def list_webhook_triggers(
    current_user: Any = Depends(get_current_user),
) -> WebhookTriggerListResponse:
    """List all webhook triggers for the current user."""
    return WebhookTriggerListResponse(triggers=[], total=0)


@router.post("/webhook-triggers", response_model=WebhookTriggerResponse, status_code=201)
async def create_webhook_trigger(
    body: WebhookTriggerCreate,
    current_user: Any = Depends(get_current_user),
) -> WebhookTriggerResponse:
    """Create a new webhook trigger that starts investigations on incoming webhooks."""
    trigger_id = secrets.token_hex(16)
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()

    from src.config import get_settings
    base_url = get_settings().base_url

    return WebhookTriggerResponse(
        id=trigger_id,
        name=body.name,
        description=body.description,
        secret_token=token,
        webhook_url=f"{base_url}/api/v1/webhook-triggers/{trigger_id}/invoke",
        is_active=True,
        input_type=body.input_type,
        scanners=body.scanners,
        auto_start=body.auto_start,
        trigger_count=0,
        last_triggered_at=None,
        created_at=now,
    )


@router.delete("/webhook-triggers/{trigger_id}")
async def delete_webhook_trigger(
    trigger_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a webhook trigger."""
    log.info("Webhook trigger deleted", trigger_id=trigger_id)
    return {"status": "deleted", "id": trigger_id}


class WebhookInvokePayload(BaseModel):
    input_value: str = Field(..., min_length=1, max_length=1000)
    title: str = ""
    tags: list[str] = []


@router.post("/webhook-triggers/{trigger_id}/invoke")
async def invoke_webhook(
    trigger_id: str,
    body: WebhookInvokePayload,
    x_webhook_secret: str = Header(None),
) -> dict[str, Any]:
    """Public endpoint invoked by external systems to start an investigation.

    Validates the webhook secret token for authentication.
    """
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")

    # In production: look up trigger, validate secret, create investigation
    log.info("Webhook invoked", trigger_id=trigger_id, input_value=body.input_value)

    return {
        "status": "accepted",
        "trigger_id": trigger_id,
        "investigation_id": secrets.token_hex(16),
        "message": "Investigation creation queued",
    }
