"""FastAPI router — Subdomain Takeover Detection via crt.sh + DNS checks."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.subdomain_takeover_models import SubdomainTakeoverModel
from src.adapters.subdomain_takeover.fetcher import scan_domain
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.subdomain_takeover.schemas import (
    SubdomainResultSchema, SubdomainTakeoverListResponse, SubdomainTakeoverRequest, SubdomainTakeoverResponse,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=SubdomainTakeoverResponse, status_code=status.HTTP_201_CREATED)
async def subdomain_takeover_scan(
    body: SubdomainTakeoverRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubdomainTakeoverResponse:
    domain = body.domain.strip()
    if not domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="domain must not be empty.")

    report = await scan_domain(domain)

    result_dict = {
        "domain": report.domain,
        "total_subdomains": report.total_subdomains,
        "vulnerable": [vars(r) for r in report.vulnerable],
        "safe": [vars(r) for r in report.safe],
    }

    model = SubdomainTakeoverModel(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        domain=domain,
        total_subdomains=report.total_subdomains,
        vulnerable_count=len(report.vulnerable),
        result=result_dict,
        created_at=datetime.now(timezone.utc),
    )
    db.add(model)
    await db.flush()

    return SubdomainTakeoverResponse(
        id=model.id,
        created_at=model.created_at,
        domain=report.domain,
        total_subdomains=report.total_subdomains,
        vulnerable=[SubdomainResultSchema(**vars(r)) for r in report.vulnerable],
        safe=[SubdomainResultSchema(**vars(r)) for r in report.safe],
    )


@router.get("/", response_model=SubdomainTakeoverListResponse)
async def list_subdomain_takeover_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SubdomainTakeoverListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(SubdomainTakeoverModel)
            .where(SubdomainTakeoverModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(SubdomainTakeoverModel)
                .where(SubdomainTakeoverModel.owner_id == current_user.id)
                .order_by(SubdomainTakeoverModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )
    return SubdomainTakeoverListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=SubdomainTakeoverResponse)
async def get_subdomain_takeover_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubdomainTakeoverResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_subdomain_takeover_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> SubdomainTakeoverModel:
    result = await db.execute(
        select(SubdomainTakeoverModel).where(
            SubdomainTakeoverModel.id == scan_id,
            SubdomainTakeoverModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(m: SubdomainTakeoverModel) -> SubdomainTakeoverResponse:
    r = m.result or {}
    return SubdomainTakeoverResponse(
        id=m.id,
        created_at=m.created_at,
        domain=m.domain,
        total_subdomains=m.total_subdomains,
        vulnerable=[SubdomainResultSchema(**s) for s in r.get("vulnerable", [])],
        safe=[SubdomainResultSchema(**s) for s in r.get("safe", [])],
    )
