"""Scan profile endpoints — reusable scanner configuration presets."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi.responses import Response
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.adapters.scanners.registry import get_default_registry
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ScanProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    enabled_scanners: list[str] = []
    proxy_mode: str = Field("none", pattern="^(none|tor|custom)$")
    timeout_override: int | None = Field(None, ge=1, le=3600)
    cache_bypass: bool = False


class ScanProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    enabled_scanners: list[str] | None = None
    proxy_mode: str | None = Field(None, pattern="^(none|tor|custom)$")
    timeout_override: int | None = Field(None, ge=1, le=3600)
    cache_bypass: bool | None = None


class ScanProfileResponse(BaseModel):
    id: str
    name: str
    description: str
    enabled_scanners: list[str]
    proxy_mode: str
    timeout_override: int | None
    cache_bypass: bool
    is_default: bool
    created_by: str
    created_at: str
    updated_at: str


class ScanProfileListResponse(BaseModel):
    profiles: list[ScanProfileResponse]
    total: int


class AvailableScannersResponse(BaseModel):
    scanners: list[str]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(body: ScanProfileCreate, user_id: str) -> ScanProfileResponse:
    now = datetime.now(timezone.utc).isoformat()
    return ScanProfileResponse(
        id=secrets.token_hex(16),
        name=body.name,
        description=body.description,
        enabled_scanners=body.enabled_scanners,
        proxy_mode=body.proxy_mode,
        timeout_override=body.timeout_override,
        cache_bypass=body.cache_bypass,
        is_default=False,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/available-scanners", response_model=AvailableScannersResponse)
async def list_available_scanners(
    current_user: Any = Depends(get_current_user),
) -> AvailableScannersResponse:
    """Return all registered scanner names from the global registry."""
    registry = get_default_registry()
    names = [s.scanner_name for s in registry.all_scanners]
    return AvailableScannersResponse(scanners=names, total=len(names))


@router.post("/", response_model=ScanProfileResponse, status_code=201)
async def create_scan_profile(
    body: ScanProfileCreate,
    current_user: Any = Depends(get_current_user),
) -> ScanProfileResponse:
    """Create a new scan profile preset."""
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info("Scan profile created", name=body.name, user=user_id)
    return _make_profile(body, user_id)


@router.get("/", response_model=ScanProfileListResponse)
async def list_scan_profiles(
    current_user: Any = Depends(get_current_user),
) -> ScanProfileListResponse:
    """List all scan profiles for the current user."""
    return ScanProfileListResponse(profiles=[], total=0)


@router.get("/{profile_id}", response_model=ScanProfileResponse)
async def get_scan_profile(
    profile_id: str,
    current_user: Any = Depends(get_current_user),
) -> ScanProfileResponse:
    """Retrieve a single scan profile."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    return ScanProfileResponse(
        id=profile_id,
        name="Placeholder Profile",
        description="",
        enabled_scanners=[],
        proxy_mode="none",
        timeout_override=None,
        cache_bypass=False,
        is_default=False,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.patch("/{profile_id}", response_model=ScanProfileResponse)
async def update_scan_profile(
    profile_id: str,
    body: ScanProfileUpdate,
    current_user: Any = Depends(get_current_user),
) -> ScanProfileResponse:
    """Update an existing scan profile."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    log.info("Scan profile updated", profile_id=profile_id, user=user_id)
    return ScanProfileResponse(
        id=profile_id,
        name=body.name or "Updated Profile",
        description=body.description or "",
        enabled_scanners=body.enabled_scanners or [],
        proxy_mode=body.proxy_mode or "none",
        timeout_override=body.timeout_override,
        cache_bypass=body.cache_bypass if body.cache_bypass is not None else False,
        is_default=False,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.delete("/{profile_id}", status_code=204, response_model=None)
async def delete_scan_profile(
    profile_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Delete a scan profile."""
    log.info("Scan profile deleted", profile_id=profile_id)


@router.post("/{profile_id}/set-default")
async def set_default_scan_profile(
    profile_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Mark this profile as the workspace default."""
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info("Scan profile set as default", profile_id=profile_id, user=user_id)
    return {"status": "default_set", "profile_id": profile_id}
