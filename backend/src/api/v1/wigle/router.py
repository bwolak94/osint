"""FastAPI router for the WiGLE WiFi geolocation module."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.wigle_models import WigleModel
from src.adapters.wigle.client import WigleClient
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.wigle.schemas import (
    WigleListResponse,
    WigleNetworkSchema,
    WigleRequest,
    WigleResponse,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()

_VALID_QUERY_TYPES = frozenset({"bssid", "ssid"})


@router.post("/", response_model=WigleResponse, status_code=status.HTTP_201_CREATED)
async def search_wigle(
    body: WigleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WigleResponse:
    if body.query_type not in _VALID_QUERY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query_type must be 'bssid' or 'ssid'.",
        )
    if not body.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query must not be empty.",
        )

    client = WigleClient()
    result = await client.search(body.query.strip(), body.query_type)

    networks_json = [n.__dict__ for n in result.networks]
    model = WigleModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        query=result.query,
        query_type=result.query_type,
        total_results=len(result.networks),
        results=networks_json,
    )
    db.add(model)
    await db.flush()
    return _to_response(model)


@router.get("/", response_model=WigleListResponse)
async def list_wigle_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WigleListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(WigleModel)
            .where(WigleModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(WigleModel)
                .where(WigleModel.owner_id == current_user.id)
                .order_by(WigleModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return WigleListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=WigleResponse)
async def get_wigle_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WigleResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_wigle_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(
    db: AsyncSession,
    scan_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> WigleModel:
    result = await db.execute(
        select(WigleModel).where(
            WigleModel.id == scan_id,
            WigleModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found.",
        )
    return model


def _to_response(model: WigleModel) -> WigleResponse:
    networks = [WigleNetworkSchema(**n) for n in (model.results or [])]
    return WigleResponse(
        id=model.id,
        query=model.query,
        query_type=model.query_type,
        total_results=model.total_results,
        results=networks,
        created_at=model.created_at,
    )
