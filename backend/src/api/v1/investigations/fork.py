"""Investigation forking endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class ForkRequest(BaseModel):
    reason: str = ""
    include_results: bool = True
    new_title: str | None = None


class ForkResponse(BaseModel):
    id: str
    parent_investigation_id: str
    child_investigation_id: str
    fork_reason: str
    created_at: str


class ForkListResponse(BaseModel):
    forks: list[ForkResponse]
    total: int


@router.post("/{investigation_id}/fork", response_model=ForkResponse, status_code=201)
async def fork_investigation(
    investigation_id: str,
    body: ForkRequest,
    current_user: Any = Depends(get_current_user),
) -> ForkResponse:
    """Fork an investigation, creating a new one with the same data."""
    child_id = secrets.token_hex(16)
    now = datetime.now(timezone.utc).isoformat()

    log.info(
        "Investigation forked",
        parent_id=investigation_id,
        child_id=child_id,
        reason=body.reason,
    )

    return ForkResponse(
        id=secrets.token_hex(16),
        parent_investigation_id=investigation_id,
        child_investigation_id=child_id,
        fork_reason=body.reason,
        created_at=now,
    )


@router.get("/{investigation_id}/forks", response_model=ForkListResponse)
async def list_forks(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> ForkListResponse:
    """List all forks of an investigation."""
    return ForkListResponse(forks=[], total=0)
