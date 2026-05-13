"""FastAPI router — ASN Intelligence via BGPView."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.asn_intel.fetcher import lookup_asn
from src.adapters.db.asn_intel_models import AsnIntelModel
from src.api.v1.asn_intel.schemas import (
    AsnIntelListResponse, AsnIntelRequest, AsnIntelResponse, AsnPeerSchema, AsnPrefixSchema,
)
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=AsnIntelResponse, status_code=status.HTTP_201_CREATED)
async def asn_intel_lookup(
    body: AsnIntelRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsnIntelResponse:
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    info = await lookup_asn(q)

    if info is None:
        result_dict: dict = {}
        found = False
        response_kwargs: dict = {}
    else:
        result_dict = {
            "asn": info.asn,
            "name": info.name,
            "description": info.description,
            "country": info.country,
            "website": info.website,
            "email_contacts": info.email_contacts,
            "abuse_contacts": info.abuse_contacts,
            "rir": info.rir,
            "prefixes_v4": [vars(p) for p in info.prefixes_v4],
            "prefixes_v6": [vars(p) for p in info.prefixes_v6],
            "peers": [vars(p) for p in info.peers],
            "upstreams": [vars(p) for p in info.upstreams],
            "downstreams": [vars(p) for p in info.downstreams],
        }
        found = True
        response_kwargs = {
            "asn": info.asn,
            "name": info.name,
            "description": info.description,
            "country": info.country,
            "website": info.website,
            "email_contacts": info.email_contacts,
            "abuse_contacts": info.abuse_contacts,
            "rir": info.rir,
            "prefixes_v4": [AsnPrefixSchema(**vars(p)) for p in info.prefixes_v4],
            "prefixes_v6": [AsnPrefixSchema(**vars(p)) for p in info.prefixes_v6],
            "peers": [AsnPeerSchema(**vars(p)) for p in info.peers],
            "upstreams": [AsnPeerSchema(**vars(p)) for p in info.upstreams],
            "downstreams": [AsnPeerSchema(**vars(p)) for p in info.downstreams],
        }

    now = datetime.now(timezone.utc)
    model = AsnIntelModel(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        query=q,
        found=found,
        result=result_dict,
        created_at=now,
    )
    db.add(model)
    await db.flush()

    return AsnIntelResponse(id=model.id, created_at=model.created_at, query=q, found=found, **response_kwargs)


@router.get("/", response_model=AsnIntelListResponse)
async def list_asn_intel_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AsnIntelListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(AsnIntelModel).where(AsnIntelModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(AsnIntelModel)
                .where(AsnIntelModel.owner_id == current_user.id)
                .order_by(AsnIntelModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )
    return AsnIntelListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=AsnIntelResponse)
async def get_asn_intel_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsnIntelResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_asn_intel_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> AsnIntelModel:
    result = await db.execute(
        select(AsnIntelModel).where(
            AsnIntelModel.id == scan_id,
            AsnIntelModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(m: AsnIntelModel) -> AsnIntelResponse:
    r = m.result or {}
    return AsnIntelResponse(
        id=m.id,
        created_at=m.created_at,
        query=m.query,
        found=m.found,
        asn=r.get("asn"),
        name=r.get("name"),
        description=r.get("description"),
        country=r.get("country"),
        website=r.get("website"),
        email_contacts=r.get("email_contacts", []),
        abuse_contacts=r.get("abuse_contacts", []),
        rir=r.get("rir"),
        prefixes_v4=[AsnPrefixSchema(**p) for p in r.get("prefixes_v4", [])],
        prefixes_v6=[AsnPrefixSchema(**p) for p in r.get("prefixes_v6", [])],
        peers=[AsnPeerSchema(**p) for p in r.get("peers", [])],
        upstreams=[AsnPeerSchema(**p) for p in r.get("upstreams", [])],
        downstreams=[AsnPeerSchema(**p) for p in r.get("downstreams", [])],
    )
