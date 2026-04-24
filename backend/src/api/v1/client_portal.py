from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/client-portal", tags=["client-portal"])

_portals: dict[str, dict] = {}


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


@router.get("/portals", response_model=list[ClientPortal])
async def list_portals():
    return [ClientPortal(**p) for p in _portals.values()]


@router.post("/portals", response_model=ClientPortal)
async def create_portal(data: CreatePortalInput):
    pid = str(uuid.uuid4())
    portal = {
        "id": pid,
        "name": data.name,
        "client_name": data.client_name,
        "engagement_id": data.engagement_id,
        "status": "active",
        "access_token": uuid.uuid4().hex,
        "allowed_sections": data.allowed_sections,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": None,
        "view_count": 0,
    }
    _portals[pid] = portal
    return ClientPortal(**portal)


@router.post("/portals/{portal_id}/invite")
async def invite_client(portal_id: str, email: str, role: str = "viewer"):
    invite = PortalInvite(
        id=str(uuid.uuid4()),
        portal_id=portal_id,
        email=email,
        role=role,
        invited_at=datetime.utcnow().isoformat(),
        accepted=False,
    )
    return invite


@router.get("/portals/{portal_id}/stats")
async def portal_stats(portal_id: str):
    return {
        "view_count": 5,
        "unique_visitors": 2,
        "last_viewed": datetime.utcnow().isoformat(),
        "sections_viewed": ["executive_summary", "findings"],
    }
