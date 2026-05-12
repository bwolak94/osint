"""FastAPI router for IMINT/GEOINT module (Domain IV, Modules 61-80).

Endpoints:
  POST   /api/v1/imint/      — Run selected modules against a target
  GET    /api/v1/imint/      — Paginated scan history
  GET    /api/v1/imint/{id}  — Single scan result
  DELETE /api/v1/imint/{id}  — Delete scan (204)
"""

from __future__ import annotations

import asyncio
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.imint_models import ImintModel
from src.adapters.scanners.registry import get_default_registry
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.imint.schemas import ImintListResponse, ImintRequest, ImintResponse
from src.core.domain.entities.types import ScanInputType
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()

# --- Module definitions per input-type group ---

_IMAGE_MODULES = [
    "exif_deep_extractor",     # 61 — hidden EXIF/GPS metadata
    "forensic_image_auditor",  # 80 — ELA manipulation detection
    "deepfake_detector",       # 71 — AI-generation artifact analysis
    "visual_landmark_match",   # 64 — Google Vision landmark detection
    "license_plate_decoder",   # 65 — OCR plate identification
    "perspective_distorter",   # 74 — homography / text region detection
    "neural_image_upscaler",   # 70 — quality metrics & upscaling links
]

_COORDINATES_MODULES = [
    "satellite_delta_mapper",  # 62 — Sentinel-2 change detection
    "chronolocator",           # 63 — sun position / shadow timing
    "weather_correlation",     # 66 — historical weather at location
    "webcam_finder",           # 67 — Shodan public cameras
    "adsb_tracker",            # 68 — ADS-B live flight data
    "maritime_tracker",        # 69 — AIS vessel tracking
    "geolocation_challenge",   # 72 — educational GeoGuessr challenge
    "street_view_pivot",       # 73 — 360° street-level imagery links
    "vegetation_soil_mapper",  # 75 — climate/biome/flora analysis
    "building_height_estimator", # 76 — shadow-based height formula
    "social_media_geofence",   # 77 — geotagged social posts
    "public_wifi_mapper",      # 78 — Wigle.net WiFi density
    "historical_map_overlay",  # 79 — old maps vs. modern satellite
]

_COORDINATES_RE = re.compile(r"^-?\d{1,3}(\.\d+)?,-?\d{1,3}(\.\d+)?")


def _detect_target_type(target: str) -> tuple[str, ScanInputType]:
    """Detect whether target is coordinates, image URL, or generic URL."""
    if _COORDINATES_RE.match(target.strip()):
        return "coordinates", ScanInputType.COORDINATES
    if target.startswith(("http://", "https://")):
        # Heuristic: image extensions → image_url, else url
        lower = target.lower().split("?")[0]
        if any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff")):
            return "image_url", ScanInputType.URL
        return "url", ScanInputType.URL
    return "url", ScanInputType.URL


def _modules_for_target(target_type: str) -> list[str]:
    if target_type == "coordinates":
        return _COORDINATES_MODULES
    return _IMAGE_MODULES


async def _run_module(scanner_name: str, target: str, input_type: ScanInputType) -> tuple[str, dict]:
    registry = get_default_registry()
    scanner = registry.get_by_name(scanner_name)
    if scanner is None:
        return scanner_name, {"found": False, "error": f"Scanner '{scanner_name}' not registered"}
    if not scanner.supports(input_type):
        return scanner_name, {"found": False, "skipped": True, "reason": f"Does not support {input_type.value}"}
    try:
        result = await scanner.scan(target, input_type)
        return scanner_name, {
            "found": result.raw_data.get("found", False),
            "data": result.raw_data,
            "error": result.error_message,
            "status": result.status.value,
        }
    except Exception as exc:
        log.warning("imint module failed", module=scanner_name, error=str(exc))
        return scanner_name, {"found": False, "error": str(exc)}


@router.post("/", response_model=ImintResponse, status_code=status.HTTP_201_CREATED)
async def run_imint(
    body: ImintRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImintResponse:
    target_type_str, input_type = _detect_target_type(body.target)
    modules_to_run = body.modules if body.modules else _modules_for_target(target_type_str)

    semaphore = asyncio.Semaphore(8)

    async def guarded(name: str) -> tuple[str, dict]:
        async with semaphore:
            return await _run_module(name, body.target, input_type)

    pairs = await asyncio.gather(*[guarded(m) for m in modules_to_run])
    results: dict = {name: data for name, data in pairs}

    model = ImintModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        target=body.target,
        target_type=target_type_str,
        modules_run=modules_to_run,
        results=results,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=ImintListResponse)
async def list_imint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ImintListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(ImintModel).where(ImintModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(ImintModel)
                .where(ImintModel.owner_id == current_user.id)
                .order_by(ImintModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return ImintListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=ImintResponse)
async def get_imint(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImintResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_imint(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> ImintModel:
    result = await db.execute(
        select(ImintModel).where(
            ImintModel.id == scan_id,
            ImintModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="IMINT scan not found.")
    return model


def _to_response(model: ImintModel) -> ImintResponse:
    return ImintResponse(
        id=model.id,
        target=model.target,
        target_type=model.target_type,
        modules_run=model.modules_run or [],
        results=model.results or {},
        created_at=model.created_at,
    )
