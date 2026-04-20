"""FastAPI router for Domain Permutation Scanner module.

Endpoints:
  POST   /api/v1/domain-permutation/      — Scan a domain for lookalike permutations
  GET    /api/v1/domain-permutation/      — Paginated scan history
  GET    /api/v1/domain-permutation/{id}  — Single scan result
  DELETE /api/v1/domain-permutation/{id}  — Delete scan (204)
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.domain_permutation_models import DomainPermutationModel
from src.adapters.domain_permutation.scanner import DomainPermutationScanner
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.domain_permutation.schemas import (
    DomainPermutationListResponse,
    DomainPermutationRequest,
    DomainPermutationResponse,
    PermutationItemSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()

_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$")


@router.post("/", response_model=DomainPermutationResponse, status_code=status.HTTP_201_CREATED)
async def scan_domain_permutations(
    body: DomainPermutationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DomainPermutationResponse:
    domain = body.domain.strip().lower()
    if not _DOMAIN_RE.match(domain):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid domain name format.")

    scanner = DomainPermutationScanner()
    result = await scanner.scan(domain)

    model = DomainPermutationModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        target_domain=result.target_domain,
        total_permutations=result.total_permutations,
        registered_count=result.registered_count,
        permutations=result.permutations,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=DomainPermutationListResponse)
async def list_domain_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DomainPermutationListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(DomainPermutationModel).where(
                DomainPermutationModel.owner_id == current_user.id
            )
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(DomainPermutationModel)
                .where(DomainPermutationModel.owner_id == current_user.id)
                .order_by(DomainPermutationModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return DomainPermutationListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=DomainPermutationResponse)
async def get_domain_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DomainPermutationResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_domain_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(
    db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID
) -> DomainPermutationModel:
    result = await db.execute(
        select(DomainPermutationModel).where(
            DomainPermutationModel.id == scan_id,
            DomainPermutationModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: DomainPermutationModel) -> DomainPermutationResponse:
    permutations = [PermutationItemSchema(**p) for p in (model.permutations or [])]
    return DomainPermutationResponse(
        id=model.id,
        target_domain=model.target_domain,
        total_permutations=model.total_permutations,
        registered_count=model.registered_count,
        permutations=permutations,
        created_at=model.created_at,
    )
