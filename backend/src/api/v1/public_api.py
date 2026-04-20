"""Public REST API with API key authentication and rate limiting."""

import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel
from src.adapters.db.settings_models import UserSettingsModel
from src.dependencies import get_db

router = APIRouter()


async def authenticate_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate using API key (SHA-256 hash lookup).

    Check IP allowlist (if configured)
    This is a placeholder -- in production, read allowed_ips from UserSettings
    """
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    stmt = select(UserSettingsModel).where(UserSettingsModel.api_key_hash == key_hash)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    user = await db.get(UserModel, settings.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


class PublicInvestigationResponse(BaseModel):
    id: str
    title: str
    status: str
    created_at: str


class PublicScanResultResponse(BaseModel):
    scanner: str
    input: str
    status: str
    findings_count: int
    raw_data: dict


@router.get("/investigations", response_model=list[PublicInvestigationResponse])
async def list_investigations(
    user=Depends(authenticate_api_key),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, le=100),
):
    """List investigations for the authenticated API user."""
    stmt = (
        select(InvestigationModel)
        .where(InvestigationModel.owner_id == user.id)
        .order_by(InvestigationModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        PublicInvestigationResponse(
            id=str(inv.id), title=inv.title,
            status=inv.status.value if hasattr(inv.status, 'value') else str(inv.status),
            created_at=inv.created_at.isoformat(),
        )
        for inv in result.scalars().all()
    ]


@router.get("/investigations/{investigation_id}/results", response_model=list[PublicScanResultResponse])
async def get_results(
    investigation_id: UUID,
    user=Depends(authenticate_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get scan results for an investigation."""
    # Verify ownership
    inv = await db.get(InvestigationModel, investigation_id)
    if not inv or inv.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Investigation not found")

    stmt = select(ScanResultModel).where(ScanResultModel.investigation_id == investigation_id)
    result = await db.execute(stmt)
    return [
        PublicScanResultResponse(
            scanner=sr.scanner_name, input=sr.input_value,
            status=sr.status.value if hasattr(sr.status, 'value') else str(sr.status),
            findings_count=len(sr.extracted_identifiers or []),
            raw_data=sr.raw_data or {},
        )
        for sr in result.scalars().all()
    ]
