"""Retest / fix-verification endpoints — trigger and track remediation verification."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_extras_models import RetestModel
from src.adapters.db.pentest_models import PentestFindingModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["retest"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RetestResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    requested_by: uuid.UUID
    status: str
    triggered_at: datetime
    completed_at: datetime | None
    result_finding_id: uuid.UUID | None
    notes: str | None

    model_config = {"from_attributes": True}


class TriggerRetestResponse(BaseModel):
    retest_id: uuid.UUID
    celery_task_id: str
    status: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _retest_or_404(retest: RetestModel | None) -> RetestModel:
    if retest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retest record not found.")
    return retest


def _to_response(m: RetestModel) -> RetestResponse:
    return RetestResponse(
        id=m.id,
        finding_id=m.finding_id,
        requested_by=m.requested_by,
        status=m.status,
        triggered_at=m.triggered_at,
        completed_at=m.completed_at,
        result_finding_id=m.result_finding_id,
        notes=m.notes,
    )


# ---------------------------------------------------------------------------
# POST /findings/{finding_id}/retest
# ---------------------------------------------------------------------------


@router.post(
    "/findings/{finding_id}/retest",
    response_model=TriggerRetestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_retest(
    finding_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> TriggerRetestResponse:
    """Create a retest record and enqueue the Celery retest task."""
    finding_stmt = select(PentestFindingModel).where(PentestFindingModel.id == finding_id)
    finding = (await db.execute(finding_stmt)).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")

    retest = RetestModel(
        id=uuid.uuid4(),
        finding_id=finding_id,
        requested_by=current_user.id,
        status="pending",
    )
    db.add(retest)
    await db.flush()
    await db.refresh(retest)

    # Enqueue Celery task
    from src.workers.retest_tasks import retest_finding

    celery_result = retest_finding.apply_async(args=[str(retest.id)], queue="pentest_light")

    log.info(
        "retest_triggered",
        retest_id=str(retest.id),
        finding_id=str(finding_id),
        celery_task_id=celery_result.id,
        user_id=str(current_user.id),
    )
    return TriggerRetestResponse(
        retest_id=retest.id,
        celery_task_id=celery_result.id,
        status="pending",
    )


# ---------------------------------------------------------------------------
# GET /findings/{finding_id}/retests
# ---------------------------------------------------------------------------


@router.get("/findings/{finding_id}/retests", response_model=list[RetestResponse])
async def list_retests(
    finding_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> list[RetestResponse]:
    finding_stmt = select(PentestFindingModel).where(PentestFindingModel.id == finding_id)
    finding = (await db.execute(finding_stmt)).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")

    stmt = (
        select(RetestModel)
        .where(RetestModel.finding_id == finding_id)
        .order_by(RetestModel.triggered_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /retests/{id}
# ---------------------------------------------------------------------------


@router.get("/retests/{retest_id}", response_model=RetestResponse)
async def get_retest(
    retest_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> RetestResponse:
    stmt = select(RetestModel).where(RetestModel.id == retest_id)
    retest = (await db.execute(stmt)).scalar_one_or_none()
    return _to_response(_retest_or_404(retest))
