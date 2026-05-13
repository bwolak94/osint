"""FastAPI router — Cross-platform Username Scanner."""
from __future__ import annotations
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.adapters.username_scanner.fetcher import scan_username
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.username_scanner.schemas import (
    PlatformResultSchema, UsernameScanRequest, UsernameScanResponse,
)
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=UsernameScanResponse)
async def username_scan(
    body: UsernameScanRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> UsernameScanResponse:
    username = body.username.strip().lstrip("@")
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username must not be empty.")
    if len(username) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username too long.")

    result = await scan_username(username)
    return UsernameScanResponse(
        username=result.username,
        total_checked=result.total_checked,
        found=[PlatformResultSchema(**vars(r)) for r in result.found],
        not_found=[PlatformResultSchema(**vars(r)) for r in result.not_found],
        errors=[PlatformResultSchema(**vars(r)) for r in result.errors],
    )
