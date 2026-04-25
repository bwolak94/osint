"""GDPR compliance endpoints.

Implements:
  POST /api/v1/gdpr/data-export        — Article 20: right to data portability
  POST /api/v1/gdpr/erasure-request    — Article 17: right to be forgotten
  GET  /api/v1/gdpr/erasure-requests   — list pending erasure requests (admin)
  POST /api/v1/gdpr/erasure-requests/{id}/execute — run erasure (admin)
  GET  /api/v1/gdpr/retention-policy   — show data retention schedule
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.models import UserModel
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/gdpr", tags=["gdpr"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]

# ---------------------------------------------------------------------------
# In-memory erasure request queue (replace with DB table in production)
# ---------------------------------------------------------------------------

_erasure_requests: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------

RETENTION_POLICY = {
    "investigation_data": {"days": 365, "description": "Investigation nodes, edges, and metadata"},
    "scan_results": {"days": 180, "description": "Pentest scan findings and reports"},
    "audit_logs": {"days": 730, "description": "Security audit trail (2 years per NIS2)"},
    "user_sessions": {"days": 30, "description": "JWT refresh tokens and session records"},
    "uploaded_evidence": {"days": 90, "description": "Screenshots and evidence files in MinIO"},
    "celery_task_results": {"days": 7, "description": "Async task results in Redis"},
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ErasureRequest(BaseModel):
    id: str
    user_id: str
    user_email: str
    requested_at: datetime
    status: str   # pending | executing | completed | rejected
    reason: str


class ErasureCreate(BaseModel):
    reason: str = "User requested data deletion per GDPR Art. 17"


class RetentionPolicyItem(BaseModel):
    data_type: str
    days: int
    description: str
    purge_after_date: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/data-export")
async def export_user_data(current_user: UserDep, db: DbDep) -> Response:
    """Export all personal data for the current user (Art. 20 portability)."""
    stmt = select(UserModel).where(UserModel.id == current_user.id)
    user_row = (await db.execute(stmt)).scalar_one_or_none()

    if user_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Collect personal data snapshot
    export_data: dict[str, Any] = {
        "export_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "request_basis": "GDPR Article 20 — Right to Data Portability",
            "format": "JSON",
        },
        "profile": {
            "id": str(user_row.id),
            "email": user_row.email,
            "subscription_tier": user_row.subscription_tier,
            "created_at": user_row.created_at.isoformat() if user_row.created_at else None,
            "tos_accepted_at": user_row.tos_accepted_at.isoformat() if getattr(user_row, "tos_accepted_at", None) else None,
        },
        "note": "Investigation, scan, and finding data are exported separately via their respective APIs.",
    }

    payload = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
    await log.ainfo("gdpr_data_export", user_id=str(current_user.id))
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="gdpr-export-{current_user.id}.json"'},
    )


@router.post("/erasure-request", status_code=status.HTTP_202_ACCEPTED)
async def request_erasure(body: ErasureCreate, current_user: UserDep, db: DbDep) -> ErasureRequest:
    """Submit a right-to-be-forgotten request (Art. 17)."""
    req_id = str(uuid.uuid4())
    stmt = select(UserModel).where(UserModel.id == current_user.id)
    user_row = (await db.execute(stmt)).scalar_one_or_none()

    record: dict[str, Any] = {
        "id": req_id,
        "user_id": str(current_user.id),
        "user_email": user_row.email if user_row else "unknown",
        "requested_at": datetime.now(timezone.utc),
        "status": "pending",
        "reason": body.reason,
    }
    _erasure_requests[req_id] = record
    await log.ainfo("gdpr_erasure_requested", request_id=req_id, user_id=str(current_user.id))
    return ErasureRequest(**record)


@router.get("/erasure-requests", response_model=list[ErasureRequest])
async def list_erasure_requests(current_user: UserDep) -> list[ErasureRequest]:
    if getattr(current_user, "role", "viewer") not in ("admin",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only.")
    return [ErasureRequest(**r) for r in _erasure_requests.values()]


@router.post("/erasure-requests/{request_id}/execute", status_code=status.HTTP_200_OK)
async def execute_erasure(
    request_id: str,
    current_user: UserDep,
    db: DbDep,
) -> dict[str, str]:
    """Irreversibly erase user data. Admin-only action."""
    if getattr(current_user, "role", "viewer") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only.")

    record = _erasure_requests.get(request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Erasure request not found.")
    if record["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already '{record['status']}'.",
        )

    record["status"] = "executing"
    user_id = uuid.UUID(record["user_id"])

    # Anonymize user record (hard delete requires FK cascade — adjust per deployment)
    await db.execute(
        delete(UserModel).where(UserModel.id == user_id)
    )
    await db.commit()

    record["status"] = "completed"
    await log.ainfo(
        "gdpr_erasure_executed",
        request_id=request_id,
        subject_user_id=str(user_id),
        executed_by=str(current_user.id),
    )
    return {"status": "completed", "request_id": request_id}


@router.get("/retention-policy", response_model=list[RetentionPolicyItem])
async def get_retention_policy(current_user: UserDep) -> list[RetentionPolicyItem]:  # noqa: ARG001
    now = datetime.now(timezone.utc)
    return [
        RetentionPolicyItem(
            data_type=dt,
            days=info["days"],
            description=info["description"],
            purge_after_date=(now + timedelta(days=info["days"])).strftime("%Y-%m-%d"),
        )
        for dt, info in RETENTION_POLICY.items()
    ]
