"""Investigation diff/comparison endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class DiffEntry(BaseModel):
    field: str
    old_value: Any
    new_value: Any
    change_type: str  # added, removed, modified


class InvestigationDiffResponse(BaseModel):
    investigation_id: str
    version_a: str
    version_b: str
    changes: list[DiffEntry]
    added_results: int
    removed_results: int
    modified_results: int


@router.get("/investigations/{investigation_id}/diff", response_model=InvestigationDiffResponse)
async def get_investigation_diff(
    investigation_id: str,
    version_a: str = Query("initial"),
    version_b: str = Query("current"),
    current_user: Any = Depends(get_current_user),
) -> InvestigationDiffResponse:
    return InvestigationDiffResponse(
        investigation_id=investigation_id,
        version_a=version_a,
        version_b=version_b,
        changes=[],
        added_results=0,
        removed_results=0,
        modified_results=0,
    )


@router.get("/investigations/{investigation_id}/versions")
async def list_investigation_versions(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    return {"versions": [], "investigation_id": investigation_id}
