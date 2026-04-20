"""FastAPI router for the Fediverse scanner module."""
from __future__ import annotations
import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.fediverse_models import FediverseModel
from src.adapters.fediverse.scanner import FediverseScanner
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.fediverse.schemas import (
    FediverseListResponse,
    FediverseProfileSchema,
    FediverseRequest,
    FediverseResponse,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


@router.post("/", response_model=FediverseResponse, status_code=status.HTTP_201_CREATED)
async def scan_fediverse(
    body: FediverseRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FediverseResponse:
    if not body.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    scanner = FediverseScanner()
    result = await scanner.scan(body.query.strip())
    profiles_json = [p.__dict__ for p in result.profiles]

    model = FediverseModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        query=result.query,
        total_results=len(result.profiles),
        platforms_searched=result.platforms_searched,
        results=profiles_json,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=FediverseListResponse)
async def list_fediverse_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FediverseListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(FediverseModel).where(FediverseModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(FediverseModel)
                .where(FediverseModel.owner_id == current_user.id)
                .order_by(FediverseModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return FediverseListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=FediverseResponse)
async def get_fediverse_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FediverseResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_fediverse_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> FediverseModel:
    result = await db.execute(
        select(FediverseModel).where(
            FediverseModel.id == scan_id,
            FediverseModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: FediverseModel) -> FediverseResponse:
    profiles = [FediverseProfileSchema(**p) for p in (model.results or [])]
    return FediverseResponse(
        id=model.id,
        query=model.query,
        total_results=model.total_results,
        platforms_searched=model.platforms_searched or [],
        results=profiles,
        created_at=model.created_at,
    )
