"""FastAPI router for Cloud Storage Exposure Scanner module."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.cloud_exposure_models import CloudExposureModel
from src.adapters.cloud_exposure.scanner import CloudExposureScanner
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.cloud_exposure.schemas import (
    BucketSchema,
    CloudExposureListResponse,
    CloudExposureRequest,
    CloudExposureResponse,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


@router.post("/", response_model=CloudExposureResponse, status_code=status.HTTP_201_CREATED)
async def scan_cloud_exposure(
    body: CloudExposureRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CloudExposureResponse:
    target = body.target.strip()
    if not target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target must not be empty.")

    scanner = CloudExposureScanner()
    result = await scanner.scan(target)

    model = CloudExposureModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        target=result.target,
        total_buckets=result.total_buckets,
        public_buckets=result.public_buckets,
        sensitive_findings=result.sensitive_findings,
        buckets=result.buckets,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=CloudExposureListResponse)
async def list_cloud_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CloudExposureListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(CloudExposureModel).where(
                CloudExposureModel.owner_id == current_user.id
            )
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(CloudExposureModel)
                .where(CloudExposureModel.owner_id == current_user.id)
                .order_by(CloudExposureModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return CloudExposureListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=CloudExposureResponse)
async def get_cloud_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CloudExposureResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_cloud_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> CloudExposureModel:
    result = await db.execute(
        select(CloudExposureModel).where(
            CloudExposureModel.id == scan_id,
            CloudExposureModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: CloudExposureModel) -> CloudExposureResponse:
    buckets = [BucketSchema(**b) for b in (model.buckets or [])]
    return CloudExposureResponse(
        id=model.id,
        target=model.target,
        total_buckets=model.total_buckets,
        public_buckets=model.public_buckets,
        sensitive_findings=model.sensitive_findings,
        buckets=buckets,
        created_at=model.created_at,
    )
