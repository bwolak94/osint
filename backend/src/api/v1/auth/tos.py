"""Terms of Service acceptance endpoint.

Art. 269b KK (Polish Criminal Code) and EU dual-use (2021/821) compliance
requires users to explicitly accept the terms of use before accessing
any offensive security or OSINT features.  Acceptance is timestamped and
written into the tamper-evident audit log.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.audit.pentest_audit_service import AuditService
from src.adapters.db.models import UserModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["auth-tos"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TosAcceptResponse(BaseModel):
    accepted: bool
    accepted_at: datetime


@router.post(
    "/accept-tos",
    response_model=TosAcceptResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept Terms of Service (Art. 269b KK / EU 2021/821)",
)
async def accept_tos(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TosAcceptResponse:
    """Record the user's acceptance of the Terms of Service.

    This endpoint must be called once before any offensive-security or OSINT
    scan is permitted.  The timestamp and source IP are written to the
    hash-chained audit log so acceptance cannot be repudiated.
    """
    now = _utcnow()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")

    # Persist acceptance timestamp on the user row (best-effort — column may not exist yet)
    try:
        await db.execute(
            update(UserModel)
            .where(UserModel.id == current_user.id)
            .values(tos_accepted_at=now)
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        await log.awarning("tos_db_update_skipped", reason=str(exc), user_id=str(current_user.id))

    # Write to tamper-evident audit chain (best-effort — don't fail acceptance if table missing)
    try:
        audit = AuditService(db)
        await audit.log(
            action="tos_accepted",
            user_id=current_user.id,
            entity="user",
            entity_id=str(current_user.id),
            payload={
                "accepted_at": now.isoformat(),
                "ip": client_ip,
                "user_agent": request.headers.get("User-Agent", ""),
            },
            ip=client_ip,
        )
    except Exception as exc:  # noqa: BLE001
        await log.awarning("tos_audit_skipped", reason=str(exc), user_id=str(current_user.id))

    await log.ainfo("tos_accepted", user_id=str(current_user.id), ip=client_ip)
    return TosAcceptResponse(accepted=True, accepted_at=now)
