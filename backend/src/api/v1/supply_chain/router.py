"""FastAPI router for Supply Chain & Package Intelligence module."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.supply_chain_models import SupplyChainModel
from src.adapters.supply_chain.scanner import SupplyChainScanner
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.supply_chain.schemas import (
    PackageSchema,
    SupplyChainListResponse,
    SupplyChainRequest,
    SupplyChainResponse,
    CveSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()

_VALID_TARGET_TYPES = frozenset({"domain", "github_user", "github_org"})


@router.post("/", response_model=SupplyChainResponse, status_code=status.HTTP_201_CREATED)
async def scan_supply_chain(
    body: SupplyChainRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupplyChainResponse:
    if body.target_type not in _VALID_TARGET_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"target_type must be one of: {', '.join(sorted(_VALID_TARGET_TYPES))}")
    if not body.target.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target must not be empty.")

    scanner = SupplyChainScanner()
    result = await scanner.scan(body.target.strip(), body.target_type)

    model = SupplyChainModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        target=result.target,
        target_type=result.target_type,
        total_packages=result.total_packages,
        total_cves=result.total_cves,
        packages=result.packages,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=SupplyChainListResponse)
async def list_supply_chain_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SupplyChainListResponse:
    offset = (page - 1) * page_size
    total = (await db.execute(select(func.count()).select_from(SupplyChainModel).where(SupplyChainModel.owner_id == current_user.id))).scalar() or 0
    rows = list((await db.execute(select(SupplyChainModel).where(SupplyChainModel.owner_id == current_user.id).order_by(SupplyChainModel.created_at.desc()).limit(page_size).offset(offset))).scalars().all())
    return SupplyChainListResponse(items=[_to_response(r) for r in rows], total=total, page=page, page_size=page_size, total_pages=math.ceil(total / page_size) if total > 0 else 0)


@router.get("/{scan_id}", response_model=SupplyChainResponse)
async def get_supply_chain_scan(scan_id: uuid.UUID, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> SupplyChainResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_supply_chain_scan(scan_id: uuid.UUID, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> SupplyChainModel:
    result = await db.execute(select(SupplyChainModel).where(SupplyChainModel.id == scan_id, SupplyChainModel.owner_id == owner_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: SupplyChainModel) -> SupplyChainResponse:
    packages = []
    for p in (model.packages or []):
        cves = [CveSchema(**c) for c in p.get("cves", [])]
        packages.append(PackageSchema(
            name=p.get("name", ""),
            registry=p.get("registry", ""),
            version=p.get("version"),
            downloads=p.get("downloads"),
            maintainer_emails=p.get("maintainer_emails", []),
            cves=cves,
            cve_count=p.get("cve_count", 0),
            risk_score=p.get("risk_score", "low"),
        ))
    return SupplyChainResponse(id=model.id, target=model.target, target_type=model.target_type, total_packages=model.total_packages, total_cves=model.total_cves, packages=packages, created_at=model.created_at)
