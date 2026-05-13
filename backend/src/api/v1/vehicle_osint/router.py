"""FastAPI router for the Vehicle OSINT module."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.vehicle_osint_models import VehicleOsintModel
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.vehicle_osint.schemas import (
    VehicleComplaintSchema,
    VehicleInfoSchema,
    VehicleOsintListResponse,
    VehicleOsintRequest,
    VehicleOsintResponse,
    VehicleRecallSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter()

_CELERY_TIMEOUT = 30  # NHTSA API calls are fast


@router.post("/", response_model=VehicleOsintResponse, status_code=status.HTTP_201_CREATED)
async def scan_vehicle_osint(
    body: VehicleOsintRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleOsintResponse:
    if not body.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    vehicles_json = await _run_scan(body.query.strip(), body.query_type)

    model = VehicleOsintModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        query=body.query.strip(),
        query_type=body.query_type,
        total_results=len(vehicles_json),
        results=vehicles_json,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=VehicleOsintListResponse)
async def list_vehicle_osint_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> VehicleOsintListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(VehicleOsintModel)
            .where(VehicleOsintModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(VehicleOsintModel)
                .where(VehicleOsintModel.owner_id == current_user.id)
                .order_by(VehicleOsintModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return VehicleOsintListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=VehicleOsintResponse)
async def get_vehicle_osint_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleOsintResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_vehicle_osint_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _run_scan(query: str, query_type: str) -> list[dict]:
    try:
        result = await _dispatch_celery(query, query_type)
        if result is not None:
            return result
    except Exception as exc:
        log.warning("vehicle_osint_celery_failed", query=query, error=str(exc))
    return []


async def _dispatch_celery(query: str, query_type: str) -> list[dict] | None:
    import asyncio

    loop = asyncio.get_event_loop()

    def _send_and_get() -> list[dict] | None:
        try:
            from src.workers.tasks.vehicle_osint_task import vehicle_osint_fetch_task
            task = vehicle_osint_fetch_task.apply_async(
                args=[query, query_type],
                queue="light",
            )
            raw = task.get(timeout=_CELERY_TIMEOUT, propagate=True)
            return raw.get("vehicles", [])
        except Exception:
            return None

    return await loop.run_in_executor(None, _send_and_get)


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> VehicleOsintModel:
    result = await db.execute(
        select(VehicleOsintModel).where(
            VehicleOsintModel.id == scan_id,
            VehicleOsintModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: VehicleOsintModel) -> VehicleOsintResponse:
    vehicles = []
    for v in (model.results or []):
        recalls = [VehicleRecallSchema(**r) for r in v.get("recalls", [])]
        complaints = [VehicleComplaintSchema(**c) for c in v.get("recent_complaints", [])]
        vehicles.append(VehicleInfoSchema(**{**v, "recalls": recalls, "recent_complaints": complaints}))
    return VehicleOsintResponse(
        id=model.id,
        query=model.query,
        query_type=model.query_type,
        total_results=model.total_results,
        results=vehicles,
        created_at=model.created_at,
    )
