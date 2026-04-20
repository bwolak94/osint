"""FastAPI router for the Image Checker module.

Endpoints:
  POST   /api/v1/image-checker/      — Upload an image and extract metadata
  GET    /api/v1/image-checker/      — Paginated history for the current user
  GET    /api/v1/image-checker/{id}  — Retrieve a single check
  DELETE /api/v1/image-checker/{id}  — Delete a check (204)
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.image_check_models import ImageCheckModel
from src.adapters.image_metadata.extractor import ImageMetadataExtractor
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.image_checker.schemas import (
    GPSDataSchema,
    ImageCheckListResponse,
    ImageCheckResponse,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

_ALLOWED_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
        "image/gif",
        "image/bmp",
    }
)


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------


@router.post("/", response_model=ImageCheckResponse, status_code=status.HTTP_201_CREATED)
async def upload_image_check(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> ImageCheckResponse:
    """Upload an image file and extract its metadata (EXIF, GPS, camera info).

    Returns the persisted check record including all extracted metadata.
    """
    file_bytes = await file.read()

    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum allowed size is {_MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    # Detect MIME type from content so callers cannot spoof via Content-Type header
    extracted = ImageMetadataExtractor().extract(file_bytes, file.filename or "upload")

    if extracted.mime_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{extracted.mime_type}'. "
                f"Allowed types: {', '.join(sorted(_ALLOWED_MIME_TYPES))}."
            ),
        )

    gps_dict: dict | None = None
    if extracted.gps is not None:
        gps_dict = {
            "latitude": extracted.gps.latitude,
            "longitude": extracted.gps.longitude,
            "altitude": extracted.gps.altitude,
            "gps_timestamp": extracted.gps.gps_timestamp,
            "maps_url": extracted.gps.maps_url,
        }

    model = ImageCheckModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        filename=extracted.filename,
        file_hash=extracted.file_hash,
        file_size=extracted.file_size,
        mime_type=extracted.mime_type,
        exif_metadata=_sanitise_tags(extracted.all_tags),
        gps_data=gps_dict,
        camera_make=extracted.camera_make,
        camera_model=extracted.camera_model,
        taken_at=extracted.taken_at,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


@router.get("/", response_model=ImageCheckListResponse)
async def list_image_checks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page (max 100)")] = 20,
) -> ImageCheckListResponse:
    """Return a paginated list of image checks belonging to the current user."""
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count())
        .select_from(ImageCheckModel)
        .where(ImageCheckModel.owner_id == current_user.id)
    )
    total = total_result.scalar() or 0

    rows_result = await db.execute(
        select(ImageCheckModel)
        .where(ImageCheckModel.owner_id == current_user.id)
        .order_by(ImageCheckModel.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    rows = list(rows_result.scalars().all())

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return ImageCheckListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# GET /{check_id}
# ---------------------------------------------------------------------------


@router.get("/{check_id}", response_model=ImageCheckResponse)
async def get_image_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImageCheckResponse:
    """Retrieve a single image check by ID.

    Returns 404 if the check does not exist or belongs to a different user.
    """
    model = await _get_check_or_404(db, check_id, current_user.id)
    return _to_response(model)


# ---------------------------------------------------------------------------
# DELETE /{check_id}
# ---------------------------------------------------------------------------


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_image_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an image check record.

    Returns 404 if the check does not exist or belongs to a different user.
    """
    model = await _get_check_or_404(db, check_id, current_user.id)
    await db.delete(model)
    await db.flush()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _get_check_or_404(
    db: AsyncSession,
    check_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> ImageCheckModel:
    result = await db.execute(
        select(ImageCheckModel).where(
            ImageCheckModel.id == check_id,
            ImageCheckModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image check not found.",
        )
    return model


def _to_response(model: ImageCheckModel) -> ImageCheckResponse:
    """Convert an ORM model to a response schema."""
    gps_schema: GPSDataSchema | None = None
    if model.gps_data:
        gps_schema = GPSDataSchema(**model.gps_data)

    return ImageCheckResponse(
        id=model.id,
        filename=model.filename,
        file_hash=model.file_hash,
        file_size=model.file_size,
        mime_type=model.mime_type,
        metadata=model.exif_metadata or {},
        gps_data=gps_schema,
        camera_make=model.camera_make,
        camera_model=model.camera_model,
        taken_at=model.taken_at,
        created_at=model.created_at,
    )


def _sanitise_tags(tags: dict) -> dict:
    """Recursively remove NaN / Inf floats to keep the JSON column valid."""
    result = {}
    for k, v in tags.items():
        result[k] = _sanitise_value(v)
    return result


def _sanitise_value(v: object) -> object:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return _sanitise_tags(v)
    if isinstance(v, list):
        return [_sanitise_value(i) for i in v]
    return v
