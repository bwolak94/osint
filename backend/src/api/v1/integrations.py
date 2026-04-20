"""External integrations endpoints (SIEM, MISP, etc.)."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.integrations.siem_adapter import SIEMAdapter
from src.adapters.integrations.misp_adapter import MISPAdapter

log = structlog.get_logger()
router = APIRouter()

_siem: SIEMAdapter | None = None
_misp: MISPAdapter | None = None

def get_siem() -> SIEMAdapter:
    global _siem
    if _siem is None:
        _siem = SIEMAdapter()
    return _siem

def get_misp() -> MISPAdapter:
    global _misp
    if _misp is None:
        _misp = MISPAdapter()
    return _misp


class SIEMForwardRequest(BaseModel):
    event_type: str = Field(..., min_length=1)
    data: dict[str, Any]


class MISPPushRequest(BaseModel):
    investigation_id: str
    title: str
    iocs: list[dict[str, Any]]


class MISPPullRequest(BaseModel):
    tags: list[str] = []
    limit: int = Field(50, ge=1, le=1000)


@router.post("/integrations/siem/forward")
async def siem_forward(
    body: SIEMForwardRequest,
    current_user: Any = Depends(get_current_user),
    siem: SIEMAdapter = Depends(get_siem),
) -> dict[str, Any]:
    """Forward an event to the configured SIEM."""
    return await siem.forward_event(body.event_type, body.data)


@router.get("/integrations/siem/test")
async def siem_test_connection(
    current_user: Any = Depends(get_current_user),
    siem: SIEMAdapter = Depends(get_siem),
) -> dict[str, Any]:
    """Test SIEM connection."""
    return await siem.test_connection()


@router.post("/integrations/misp/push")
async def misp_push(
    body: MISPPushRequest,
    current_user: Any = Depends(get_current_user),
    misp: MISPAdapter = Depends(get_misp),
) -> dict[str, Any]:
    """Push investigation data to MISP."""
    return await misp.push_event(body.investigation_id, body.title, body.iocs)


@router.post("/integrations/misp/pull")
async def misp_pull(
    body: MISPPullRequest,
    current_user: Any = Depends(get_current_user),
    misp: MISPAdapter = Depends(get_misp),
) -> dict[str, Any]:
    """Pull events from MISP."""
    return await misp.pull_events(body.tags or None, body.limit)


@router.get("/integrations/misp/test")
async def misp_test_connection(
    current_user: Any = Depends(get_current_user),
    misp: MISPAdapter = Depends(get_misp),
) -> dict[str, Any]:
    """Test MISP connection."""
    return await misp.test_connection()
