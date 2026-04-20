"""Browser extension API endpoints."""
import secrets
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class QuickScanRequest(BaseModel):
    url: str = ""
    selected_text: str = ""
    page_title: str = ""
    input_value: str = Field(..., min_length=1)
    input_type: str = Field(..., pattern="^(email|phone|username|domain|ip_address|url)$")


class QuickScanResponse(BaseModel):
    scan_id: str
    status: str
    input_value: str
    input_type: str
    investigation_url: str | None


class ExtensionContextResponse(BaseModel):
    detected_entities: list[dict[str, str]]
    page_url: str


class ExtensionStatusResponse(BaseModel):
    authenticated: bool
    user_email: str | None
    subscription_tier: str | None
    scans_remaining: int


@router.post("/extension/quick-scan", response_model=QuickScanResponse)
async def extension_quick_scan(
    body: QuickScanRequest, current_user: Any = Depends(get_current_user)
) -> QuickScanResponse:
    """Quick scan from browser extension context."""
    scan_id = secrets.token_hex(16)
    log.info("Extension quick scan", input_value=body.input_value, input_type=body.input_type)
    return QuickScanResponse(
        scan_id=scan_id,
        status="queued",
        input_value=body.input_value,
        input_type=body.input_type,
        investigation_url=None,
    )


@router.post("/extension/analyze-page")
async def analyze_page(
    body: dict[str, str], current_user: Any = Depends(get_current_user)
) -> ExtensionContextResponse:
    """Extract entities from page content sent by browser extension."""
    import re

    text = body.get("text", "")
    url = body.get("url", "")
    entities: list[dict[str, str]] = []

    for email in set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)):
        entities.append({"value": email, "type": "email"})

    for ip in set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)):
        entities.append({"value": ip, "type": "ip_address"})

    return ExtensionContextResponse(detected_entities=entities, page_url=url)


@router.get("/extension/status", response_model=ExtensionStatusResponse)
async def extension_status(
    current_user: Any = Depends(get_current_user),
) -> ExtensionStatusResponse:
    """Get browser extension connection status."""
    email = str(getattr(current_user, "email", None))
    tier = str(getattr(current_user, "subscription_tier", "free"))
    return ExtensionStatusResponse(
        authenticated=True,
        user_email=email,
        subscription_tier=tier,
        scans_remaining=100,
    )
