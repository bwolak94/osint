"""FastAPI router for MAC Address Lookup module.

Endpoints:
  POST   /api/v1/mac-lookup/      — Submit MAC address for lookup
  GET    /api/v1/mac-lookup/      — Paginated history
  GET    /api/v1/mac-lookup/{id}  — Single record
  DELETE /api/v1/mac-lookup/{id}  — Delete record (204)
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.mac_lookup_models import MacLookupModel
from src.adapters.mac_lookup.resolver import MacLookupResolver
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.mac_lookup.schemas import MacLookupListResponse, MacLookupRequest, MacLookupResponse
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


@router.post("/", response_model=MacLookupResponse, status_code=status.HTTP_201_CREATED)
async def lookup_mac(
    body: MacLookupRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MacLookupResponse:
    resolver = MacLookupResolver()
    info = await resolver.resolve(body.mac_address)

    if "error" in info.raw_data and "Invalid" in info.raw_data.get("error", ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MAC address format.")

    model = MacLookupModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        mac_address=info.mac_address,
        oui_prefix=info.oui_prefix,
        manufacturer=info.manufacturer,
        manufacturer_country=info.manufacturer_country,
        device_type=info.device_type,
        is_private=info.is_private,
        is_multicast=info.is_multicast,
        raw_data=info.raw_data,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=MacLookupListResponse)
async def list_mac_lookups(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MacLookupListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(MacLookupModel).where(MacLookupModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(MacLookupModel)
                .where(MacLookupModel.owner_id == current_user.id)
                .order_by(MacLookupModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return MacLookupListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{lookup_id}", response_model=MacLookupResponse)
async def get_mac_lookup(
    lookup_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MacLookupResponse:
    return _to_response(await _get_or_404(db, lookup_id, current_user.id))


@router.delete("/{lookup_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_mac_lookup(
    lookup_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, lookup_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, lookup_id: uuid.UUID, owner_id: uuid.UUID) -> MacLookupModel:
    result = await db.execute(
        select(MacLookupModel).where(
            MacLookupModel.id == lookup_id,
            MacLookupModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MAC lookup not found.")
    return model


def _to_response(model: MacLookupModel) -> MacLookupResponse:
    return MacLookupResponse(
        id=model.id,
        mac_address=model.mac_address,
        oui_prefix=model.oui_prefix,
        manufacturer=model.manufacturer,
        manufacturer_country=model.manufacturer_country,
        device_type=model.device_type,
        is_private=model.is_private,
        is_multicast=model.is_multicast,
        raw_data=model.raw_data or {},
        created_at=model.created_at,
    )
