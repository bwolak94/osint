"""Scheduled re-scan management — periodic monitoring with change-detection alerts."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import async_session_factory
from src.adapters.db.models import InvestigationModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.utils.time import utcnow

router = APIRouter()

# In a real deployment these are stored in a dedicated scheduled_rescans table.
# For the initial implementation we store them in the investigation's metadata
# and rely on Celery beat to pick them up.

_ALLOWED_INTERVALS = {"daily", "weekly", "monthly"}


class ScheduledRescanRequest(BaseModel):
    interval: Literal["daily", "weekly", "monthly"]
    notify_on_change: bool = True
    scanner_profile: str = "standard"


class ScheduledRescanResponse(BaseModel):
    investigation_id: str
    interval: str
    notify_on_change: bool
    scanner_profile: str
    next_run_at: str


@router.post(
    "/investigations/{investigation_id}/scheduled-rescan",
    response_model=ScheduledRescanResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["scheduled-rescan"],
)
async def create_scheduled_rescan(
    investigation_id: str,
    body: ScheduledRescanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> ScheduledRescanResponse:
    """Schedule periodic re-scans for an investigation."""
    inv_id = uuid.UUID(investigation_id)
    inv = (
        await db.execute(select(InvestigationModel).where(InvestigationModel.id == inv_id))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    from datetime import timedelta

    interval_delta = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }[body.interval]

    next_run = utcnow() + interval_delta

    # Persist schedule in investigation metadata
    schedule_meta = {
        "scheduled_rescan": {
            "interval": body.interval,
            "notify_on_change": body.notify_on_change,
            "scanner_profile": body.scanner_profile,
            "next_run_at": next_run.isoformat(),
            "created_by": str(current_user.id),
        }
    }
    # Merge into existing seed_inputs metadata (seed_inputs is a JSONB dict)
    if isinstance(inv.seed_inputs, dict):
        inv.seed_inputs = {**inv.seed_inputs, **schedule_meta}
    await db.commit()

    return ScheduledRescanResponse(
        investigation_id=investigation_id,
        interval=body.interval,
        notify_on_change=body.notify_on_change,
        scanner_profile=body.scanner_profile,
        next_run_at=next_run.isoformat(),
    )


@router.delete(
    "/investigations/{investigation_id}/scheduled-rescan",
    status_code=status.HTTP_204_NO_CONTENT, response_model=None,
    tags=["scheduled-rescan"],
)
async def delete_scheduled_rescan(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> None:
    """Cancel a scheduled re-scan."""
    inv_id = uuid.UUID(investigation_id)
    inv = (
        await db.execute(select(InvestigationModel).where(InvestigationModel.id == inv_id))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if isinstance(inv.seed_inputs, dict):
        inv.seed_inputs = {k: v for k, v in inv.seed_inputs.items() if k != "scheduled_rescan"}
    await db.commit()
