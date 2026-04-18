"""API versioning lifecycle endpoints."""
from datetime import datetime, timezone
from typing import Any
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

API_VERSIONS = [
    {"version": "v1", "status": "stable", "released": "2025-01-01", "sunset": None, "changes": "Initial release with core OSINT features"},
    {"version": "v2-beta", "status": "beta", "released": "2026-04-01", "sunset": None, "changes": "GraphQL support, enhanced search, new scanners"},
]

class APIVersionInfo(BaseModel):
    version: str
    status: str
    released: str
    sunset: str | None
    changes: str

class APIVersionsResponse(BaseModel):
    versions: list[APIVersionInfo]
    current: str
    latest: str

class DeprecationNotice(BaseModel):
    endpoint: str
    deprecated_since: str
    sunset_date: str | None
    replacement: str
    message: str

@router.get("/api-versions", response_model=APIVersionsResponse)
async def list_api_versions() -> APIVersionsResponse:
    """List all API versions and their lifecycle status."""
    return APIVersionsResponse(
        versions=[APIVersionInfo(**v) for v in API_VERSIONS],
        current="v1",
        latest="v1",
    )

@router.get("/api-versions/deprecations")
async def list_deprecations(current_user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """List deprecated endpoints and their replacements."""
    return {"deprecations": [], "total": 0}

@router.get("/api-versions/{version}")
async def get_version_info(version: str) -> APIVersionInfo | dict[str, str]:
    """Get details about a specific API version."""
    for v in API_VERSIONS:
        if v["version"] == version:
            return APIVersionInfo(**v)
    return {"error": "Version not found"}
