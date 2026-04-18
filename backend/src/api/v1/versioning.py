"""Investigation versioning endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class VersionResponse(BaseModel):
    id: str
    investigation_id: str
    version_number: int
    change_summary: str
    created_by: str
    created_at: str


class VersionListResponse(BaseModel):
    versions: list[VersionResponse]
    total: int


class VersionCreateRequest(BaseModel):
    change_summary: str = ""


@router.get("/investigations/{investigation_id}/versions", response_model=VersionListResponse)
async def list_versions(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> VersionListResponse:
    return VersionListResponse(versions=[], total=0)


@router.post("/investigations/{investigation_id}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    investigation_id: str,
    body: VersionCreateRequest,
    current_user: Any = Depends(get_current_user),
) -> VersionResponse:
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    return VersionResponse(
        id=secrets.token_hex(16),
        investigation_id=investigation_id,
        version_number=1,
        change_summary=body.change_summary,
        created_by=user_id,
        created_at=now,
    )


@router.get("/investigations/{investigation_id}/versions/{version_id}")
async def get_version(
    investigation_id: str,
    version_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "id": version_id,
        "investigation_id": investigation_id,
        "snapshot_data": {},
        "version_number": 1,
    }


@router.post("/investigations/{investigation_id}/versions/{version_id}/restore")
async def restore_version(
    investigation_id: str,
    version_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    log.info("Version restored", investigation_id=investigation_id, version_id=version_id)
    return {"status": "restored", "version_id": version_id}
