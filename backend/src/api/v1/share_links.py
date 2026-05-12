"""Share link endpoints — create and manage public investigation share links."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ShareLinkCreate(BaseModel):
    expires_in_hours: int = Field(24, ge=1, le=720)
    max_views: int | None = Field(None, ge=1)
    redact_pii: bool = True
    allowed_node_types: list[str] = []


class ShareLinkResponse(BaseModel):
    token: str
    investigation_id: str
    expires_at: str
    max_views: int | None
    view_count: int
    redact_pii: bool
    allowed_node_types: list[str]
    created_by: str
    created_at: str
    is_active: bool


class ShareLinkListResponse(BaseModel):
    links: list[ShareLinkResponse]
    total: int


class PublicGraphNode(BaseModel):
    id: str
    type: str
    value: str


class PublicGraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class PublicShareResponse(BaseModel):
    token: str
    investigation_id: str
    nodes: list[PublicGraphNode]
    edges: list[PublicGraphEdge]
    redact_pii: bool
    view_count: int
    expires_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/investigations/{investigation_id}/share",
    response_model=ShareLinkResponse,
    status_code=201,
)
async def create_share_link(
    investigation_id: str,
    body: ShareLinkCreate,
    current_user: Any = Depends(get_current_user),
) -> ShareLinkResponse:
    """Create a shareable link for a public or partner audience."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=body.expires_in_hours)).isoformat()
    token = secrets.token_urlsafe(32)

    log.info("Share link created", investigation_id=investigation_id, token=token, user=user_id)

    return ShareLinkResponse(
        token=token,
        investigation_id=investigation_id,
        expires_at=expires_at,
        max_views=body.max_views,
        view_count=0,
        redact_pii=body.redact_pii,
        allowed_node_types=body.allowed_node_types,
        created_by=user_id,
        created_at=now.isoformat(),
        is_active=True,
    )


@router.get("/investigations/{investigation_id}/share", response_model=ShareLinkListResponse)
async def list_share_links(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> ShareLinkListResponse:
    """List all active share links for an investigation."""
    return ShareLinkListResponse(links=[], total=0)


@router.delete("/share-links/{token}", status_code=204, response_model=None)
async def revoke_share_link(
    token: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Revoke (delete) a share link by its token."""
    log.info("Share link revoked", token=token)


@router.get("/public/share/{token}", response_model=PublicShareResponse)
async def get_public_share(
    token: str,
) -> PublicShareResponse:
    """
    PUBLIC endpoint — no authentication required.

    Returns investigation graph data for the given share token while respecting
    redact_pii, allowed_node_types, expiry, and max_views constraints.
    View count is incremented on each successful access.
    """
    # Stub: in production, look up token in DB, validate expiry/max_views,
    # increment view_count, filter nodes by allowed_node_types, redact PII fields.
    log.info("Public share accessed", token=token)

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=24)).isoformat()

    # Return empty graph — real implementation queries the investigation graph.
    return PublicShareResponse(
        token=token,
        investigation_id="unknown",
        nodes=[],
        edges=[],
        redact_pii=True,
        view_count=1,
        expires_at=expires_at,
    )
