"""Per-workspace scanner API quota management."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import ScannerQuotaModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db
from src.utils.time import utcnow

router = APIRouter()

_ALERT_THRESHOLD = 0.80  # Alert when 80% of quota is consumed


class QuotaStatus(BaseModel):
    workspace_id: str
    scanner_name: str
    monthly_limit: int
    requests_used: int
    usage_pct: float
    alerts_enabled: bool
    period_start: str
    period_end: str


class QuotaListResponse(BaseModel):
    quotas: list[QuotaStatus]
    total_scanners: int
    over_limit: int
    near_limit: int


class SetQuotaRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "scanner_name": "shodan_scanner",
        "requests_limit": 1000,
        "workspace_id": None,
    }}}

    scanner_name: str
    requests_limit: int
    workspace_id: str | None = None  # defaults to user's workspace


@router.get(
    "/scanner-quota",
    response_model=QuotaListResponse,
    tags=["scanner-quota"],
)
async def list_quotas(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotaListResponse:
    """List quota status for all scanners in a workspace."""
    ws_id = workspace_id or str(current_user.id)

    rows = (
        await db.execute(
            select(ScannerQuotaModel).where(ScannerQuotaModel.workspace_id == ws_id)
        )
    ).scalars().all()

    quotas = [
        QuotaStatus(
            workspace_id=row.workspace_id,
            scanner_name=row.scanner_name,
            requests_used=row.requests_used,
            monthly_limit=row.requests_limit,
            usage_pct=row.requests_used / row.requests_limit if row.requests_limit else 0.0,
            alerts_enabled=(row.requests_used / row.requests_limit >= _ALERT_THRESHOLD) if row.requests_limit else False,
            period_start=row.period_start.isoformat(),
            period_end=row.period_end.isoformat(),
        )
        for row in rows
    ]

    return QuotaListResponse(
        quotas=quotas,
        total_scanners=len(quotas),
        over_limit=sum(1 for q in quotas if q.monthly_limit > 0 and q.requests_used >= q.monthly_limit),
        near_limit=sum(1 for q in quotas if q.usage_pct >= _ALERT_THRESHOLD and q.requests_used < q.monthly_limit),
    )


@router.post(
    "/scanner-quota",
    response_model=QuotaStatus,
    tags=["scanner-quota"],
)
async def set_quota(
    body: SetQuotaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotaStatus:
    """Create or update the quota limit for a scanner in a workspace."""
    # Enforce workspace isolation: only allow the user's own workspace
    user_workspace = str(current_user.id)
    if body.workspace_id is not None and body.workspace_id != user_workspace:
        raise HTTPException(
            status_code=403,
            detail="Cannot set quota for a workspace you do not own",
        )
    ws_id = user_workspace
    now = utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Month-end approximation
    period_end = (period_start + timedelta(days=32)).replace(day=1)

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = (
        pg_insert(ScannerQuotaModel)
        .values(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            scanner_name=body.scanner_name,
            period_start=period_start,
            period_end=period_end,
            requests_used=0,
            requests_limit=body.requests_limit,
        )
        .on_conflict_do_update(
            index_elements=["workspace_id", "scanner_name"],
            set_={"requests_limit": body.requests_limit},
        )
    )
    await db.execute(stmt)
    await db.commit()

    row = (
        await db.execute(
            select(ScannerQuotaModel).where(
                ScannerQuotaModel.workspace_id == ws_id,
                ScannerQuotaModel.scanner_name == body.scanner_name,
            )
        )
    ).scalar_one()

    return QuotaStatus(
        workspace_id=ws_id,
        scanner_name=row.scanner_name,
        requests_used=row.requests_used,
        monthly_limit=row.requests_limit,
        usage_pct=row.requests_used / row.requests_limit if row.requests_limit else 0.0,
        alerts_enabled=(row.requests_used / row.requests_limit >= _ALERT_THRESHOLD) if row.requests_limit else False,
        period_start=row.period_start.isoformat(),
        period_end=row.period_end.isoformat(),
    )


async def increment_quota(scanner_name: str, workspace_id: str, db: AsyncSession) -> None:
    """Increment usage counter for a scanner. Call from scanner infrastructure."""
    from sqlalchemy import update

    now = utcnow()
    await db.execute(
        update(ScannerQuotaModel)
        .where(
            ScannerQuotaModel.workspace_id == workspace_id,
            ScannerQuotaModel.scanner_name == scanner_name,
        )
        .values(requests_used=ScannerQuotaModel.requests_used + 1, last_request_at=now)
    )
    await db.commit()
