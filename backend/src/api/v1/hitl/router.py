"""HITL (Human-in-the-Loop) approval gate API.

Endpoints:
  GET  /hitl/pending        — list pending HITL requests for the current user
  GET  /hitl/{id}           — get a single HITL request
  POST /hitl/{id}/approve   — approve with optional comment
  POST /hitl/{id}/reject    — reject with a required reason
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.audit.pentest_actions import PentestAction
from src.adapters.audit.pentest_audit_service import AuditService
from src.adapters.db.pentest_models import HitlRequestModel
from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["pentest-hitl"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(require_pentester)]

# Redis key pattern: hitl:{hitl_id}:decision  — value: "approved" | "rejected" | "expired"
_REDIS_TTL_SECONDS = 35 * 60  # 35 minutes (5 min grace above 30 min timeout)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class HITLRequestResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    scan_step_id: uuid.UUID | None
    action: str
    target_info: dict[str, Any] | None
    payload: str | None
    status: str
    requested_at: datetime
    resolved_at: datetime | None
    resolved_by: uuid.UUID | None

    model_config = {"from_attributes": True}


class HITLDecisionRequest(BaseModel):
    comment: str | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(m: HitlRequestModel) -> HITLRequestResponse:
    return HITLRequestResponse(
        id=m.id,
        scan_id=m.scan_id,
        scan_step_id=m.scan_step_id,
        action=m.action,
        target_info=m.target_info,
        payload=m.payload,
        status=m.status,
        requested_at=m.requested_at,
        resolved_at=m.resolved_at,
        resolved_by=m.resolved_by,
    )


async def _get_hitl_or_404(db: AsyncSession, hitl_id: uuid.UUID) -> HitlRequestModel:
    stmt = select(HitlRequestModel).where(HitlRequestModel.id == hitl_id)
    hitl = (await db.execute(stmt)).scalar_one_or_none()
    if hitl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HITL request not found.")
    return hitl


async def _set_redis_decision(request: Request, hitl_id: uuid.UUID, decision: str) -> None:
    """Write the HITL decision to Redis so the orchestrator can poll it."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        await log.awarn("redis_unavailable_hitl_decision", hitl_id=str(hitl_id))
        return
    key = f"hitl:{hitl_id}:decision"
    await redis.set(key, decision, ex=_REDIS_TTL_SECONDS)


# ---------------------------------------------------------------------------
# GET /hitl/pending
# ---------------------------------------------------------------------------


@router.get("/pending", response_model=list[HITLRequestResponse])
async def get_pending_hitl(
    current_user: UserDep,
    db: DbDep,
) -> list[HITLRequestResponse]:
    """Return all pending HITL requests. Pentesters see their own scan requests."""
    stmt = (
        select(HitlRequestModel)
        .where(HitlRequestModel.status == "pending")
        .order_by(HitlRequestModel.requested_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /hitl/{hitl_id}
# ---------------------------------------------------------------------------


@router.get("/{hitl_id}", response_model=HITLRequestResponse)
async def get_hitl(
    hitl_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> HITLRequestResponse:
    """Return a single HITL request by ID."""
    hitl = await _get_hitl_or_404(db, hitl_id)
    return _to_response(hitl)


# ---------------------------------------------------------------------------
# POST /hitl/{hitl_id}/approve
# ---------------------------------------------------------------------------


@router.post("/{hitl_id}/approve", response_model=HITLRequestResponse)
async def approve_hitl(
    hitl_id: uuid.UUID,
    body: HITLDecisionRequest,
    request: Request,
    current_user: UserDep,
    db: DbDep,
) -> HITLRequestResponse:
    """Approve a pending HITL request.

    Updates the DB record, writes the decision to Redis so the orchestrator
    can resume, and appends a tamper-evident audit log entry.
    """
    hitl = await _get_hitl_or_404(db, hitl_id)

    if hitl.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"HITL request is already in state '{hitl.status}'.",
        )

    hitl.status = "approved"
    hitl.resolved_at = _utcnow()
    hitl.resolved_by = current_user.id
    await db.flush()

    await _set_redis_decision(request, hitl_id, "approved")

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.HITL_APPROVED,
        user_id=current_user.id,
        entity="hitl_request",
        entity_id=str(hitl_id),
        payload={
            "action": hitl.action,
            "target": hitl.target_info,
            "comment": body.comment,
        },
    )

    await log.ainfo(
        "hitl_approved",
        hitl_id=str(hitl_id),
        scan_id=str(hitl.scan_id),
        approver=str(current_user.id),
    )

    return _to_response(hitl)


# ---------------------------------------------------------------------------
# POST /hitl/{hitl_id}/reject
# ---------------------------------------------------------------------------


@router.post("/{hitl_id}/reject", response_model=HITLRequestResponse)
async def reject_hitl(
    hitl_id: uuid.UUID,
    body: HITLDecisionRequest,
    request: Request,
    current_user: UserDep,
    db: DbDep,
) -> HITLRequestResponse:
    """Reject a pending HITL request.

    The ``reason`` field is recommended but not enforced at the schema level
    so callers can provide it in either the ``reason`` or ``comment`` field.
    """
    hitl = await _get_hitl_or_404(db, hitl_id)

    if hitl.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"HITL request is already in state '{hitl.status}'.",
        )

    hitl.status = "rejected"
    hitl.resolved_at = _utcnow()
    hitl.resolved_by = current_user.id
    await db.flush()

    await _set_redis_decision(request, hitl_id, "rejected")

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.HITL_REJECTED,
        user_id=current_user.id,
        entity="hitl_request",
        entity_id=str(hitl_id),
        payload={
            "action": hitl.action,
            "target": hitl.target_info,
            "reason": body.reason or body.comment,
        },
    )

    await log.ainfo(
        "hitl_rejected",
        hitl_id=str(hitl_id),
        scan_id=str(hitl.scan_id),
        rejector=str(current_user.id),
    )

    return _to_response(hitl)
