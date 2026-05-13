"""Client Portal — persisted to PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.client_portal_models import ClientPortalModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/client-portal", tags=["client-portal"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class ClientPortal(BaseModel):
    id: str
    name: str
    client_name: str
    engagement_id: str
    status: str
    access_token: str
    allowed_sections: list[str]
    created_at: str
    expires_at: Optional[str]
    view_count: int


class PortalInvite(BaseModel):
    id: str
    portal_id: str
    email: str
    role: str
    invited_at: str
    accepted: bool


class CreatePortalInput(BaseModel):
    name: str
    client_name: str
    engagement_id: str
    allowed_sections: list[str] = ["executive_summary", "findings", "remediation_status"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_schema(m: ClientPortalModel) -> ClientPortal:
    return ClientPortal(
        id=str(m.id),
        name=m.name,
        client_name=m.client_name,
        engagement_id=m.engagement_id,
        status=m.status,
        access_token=m.access_token,
        allowed_sections=m.allowed_sections or [],
        created_at=m.created_at.isoformat(),
        expires_at=m.expires_at.isoformat() if m.expires_at else None,
        view_count=m.view_count,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/portals", response_model=list[ClientPortal])
async def list_portals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ClientPortal]:
    rows = (
        await db.execute(
            select(ClientPortalModel)
            .where(ClientPortalModel.owner_id == current_user.id)
            .order_by(ClientPortalModel.created_at.desc())
        )
    ).scalars().all()
    return [_to_schema(r) for r in rows]


@router.post("/portals", response_model=ClientPortal, status_code=status.HTTP_201_CREATED)
async def create_portal(
    data: CreatePortalInput,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClientPortal:
    model = ClientPortalModel(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        name=data.name,
        client_name=data.client_name,
        engagement_id=data.engagement_id,
        status="active",
        access_token=uuid.uuid4().hex,
        allowed_sections=data.allowed_sections,
        view_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(model)
    await db.flush()
    log.info("client_portal_created", portal_id=str(model.id), owner=str(current_user.id))
    return _to_schema(model)


@router.delete("/portals/{portal_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_portal(
    portal_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    model = await _get_or_404(db, portal_id, current_user.id)
    await db.delete(model)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/portals/{portal_id}/invite")
async def invite_client(
    portal_id: str,
    email: str,
    role: str = "viewer",
    _: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> PortalInvite:
    return PortalInvite(
        id=str(uuid.uuid4()),
        portal_id=portal_id,
        email=email,
        role=role,
        invited_at=datetime.now(timezone.utc).isoformat(),
        accepted=False,
    )


@router.get("/portals/{portal_id}/stats")
async def portal_stats(
    portal_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    model = await _get_or_404(db, portal_id, current_user.id)
    return {
        "view_count": model.view_count,
        "unique_visitors": 0,
        "last_viewed": None,
        "sections_viewed": model.allowed_sections,
    }


async def _get_or_404(db: AsyncSession, portal_id: str, owner_id: uuid.UUID) -> ClientPortalModel:
    try:
        pid = uuid.UUID(portal_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found.")
    result = await db.execute(
        select(ClientPortalModel).where(
            ClientPortalModel.id == pid,
            ClientPortalModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found.")
    return model
