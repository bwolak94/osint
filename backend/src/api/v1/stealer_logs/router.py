"""FastAPI router for Stealer Log Intelligence module."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.stealer_log_models import StealerLogModel
from src.adapters.stealer_logs.client import StealerLogClient
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.stealer_logs.schemas import (
    InfectionSchema,
    StealerLogListResponse,
    StealerLogRequest,
    StealerLogResponse,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()

_VALID_QUERY_TYPES = frozenset({"email", "domain", "ip"})


@router.post("/", response_model=StealerLogResponse, status_code=status.HTTP_201_CREATED)
async def query_stealer_logs(
    body: StealerLogRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StealerLogResponse:
    if body.query_type not in _VALID_QUERY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"query_type must be one of: {', '.join(sorted(_VALID_QUERY_TYPES))}",
        )
    if not body.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    client = StealerLogClient()
    result = await client.query(body.query.strip(), body.query_type)

    model = StealerLogModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        query=result.query,
        query_type=result.query_type,
        total_infections=result.total_infections,
        infections=result.infections,
        sources_checked=result.sources_checked,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=StealerLogListResponse)
async def list_stealer_checks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StealerLogListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(StealerLogModel).where(
                StealerLogModel.owner_id == current_user.id
            )
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(StealerLogModel)
                .where(StealerLogModel.owner_id == current_user.id)
                .order_by(StealerLogModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return StealerLogListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{check_id}", response_model=StealerLogResponse)
async def get_stealer_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StealerLogResponse:
    return _to_response(await _get_or_404(db, check_id, current_user.id))


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_stealer_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, check_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, check_id: uuid.UUID, owner_id: uuid.UUID) -> StealerLogModel:
    result = await db.execute(
        select(StealerLogModel).where(
            StealerLogModel.id == check_id,
            StealerLogModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stealer log check not found.")
    return model


def _to_response(model: StealerLogModel) -> StealerLogResponse:
    infections = [InfectionSchema(**i) for i in (model.infections or [])]
    return StealerLogResponse(
        id=model.id,
        query=model.query,
        query_type=model.query_type,
        total_infections=model.total_infections,
        infections=infections,
        sources_checked=model.sources_checked or [],
        created_at=model.created_at,
    )
