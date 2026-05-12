"""FastAPI router for SOCMINT (Social Media Intelligence) module.

Endpoints:
  POST   /api/v1/socmint/      — Run selected SOCMINT modules against a target
  GET    /api/v1/socmint/      — Paginated scan history
  GET    /api/v1/socmint/{id}  — Single scan result
  DELETE /api/v1/socmint/{id}  — Delete scan (204)

SOCMINT Module Groups (modules 21-40 + Sock Puppet Manager):
  - Identity Discovery: sherlock, whatsmyname, socialscan, maigret
  - Behavioral Analysis: activity_heatmap, language_stylometrics
  - Profile Intelligence: bio_link_extractor, profile_credibility_scorer
  - Network Analysis: linkedin, reddit
  - Contact Discovery: holehe, phone (phone targets only)
  - Historical: deleted_post_finder, wayback_cdx
"""

from __future__ import annotations

import asyncio
import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.socmint_models import SocmintModel
from src.adapters.scanners.registry import get_default_registry
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.socmint.schemas import (
    SocmintListResponse,
    SocmintRequest,
    SocmintResponse,
)
from src.core.domain.entities.types import ScanInputType
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()

# Module → scanner name mapping; grouped by SOCMINT domain category
_SOCMINT_MODULE_MAP: dict[str, str] = {
    # Module 21: Username Cross-Check
    "username_crosscheck": "sherlock",
    # Module 21b: Extended username enumeration
    "username_maigret": "maigret",
    "username_whatsmyname": "whatsmyname",
    "username_socialscan": "socialscan",
    # Module 25: Activity Heatmap
    "activity_heatmap": "activity_heatmap",
    # Module 27: Bio Link Extractor
    "bio_link_extractor": "bio_link_extractor",
    # Module 29: Language Stylometrics
    "language_stylometrics": "language_stylometrics",
    # Module 30: Historical snapshots (via Wayback CDX)
    "historical_snapshots": "wayback_cdx",
    # Module 34: Profile Credibility Scorer
    "profile_credibility": "profile_credibility_scorer",
    # Module 37: LinkedIn Network Miner
    "linkedin_network": "linkedin",
    # Module 38: Reddit Karma Analysis
    "reddit_karma": "reddit",
    # Module 39: Deleted Post Finder
    "deleted_post_finder": "deleted_post_finder",
    # Module 35: Contact Discovery (email → social)
    "contact_discovery": "holehe",
}

# Default module selection for USERNAME targets
_DEFAULT_USERNAME_MODULES = [
    "username_crosscheck",
    "username_maigret",
    "activity_heatmap",
    "bio_link_extractor",
    "language_stylometrics",
    "profile_credibility",
    "reddit_karma",
    "deleted_post_finder",
    "historical_snapshots",
]

# Default module selection for EMAIL targets
_DEFAULT_EMAIL_MODULES = [
    "contact_discovery",
    "username_crosscheck",
]

# Default module selection for PHONE targets
_DEFAULT_PHONE_MODULES: list[str] = []  # phone scanner is in main registry


def _detect_input_type(target_type: str) -> ScanInputType:
    """Map SOCMINT target_type string to ScanInputType enum."""
    mapping: dict[str, ScanInputType] = {
        "username": ScanInputType.USERNAME,
        "email": ScanInputType.EMAIL,
        "phone": ScanInputType.PHONE,
        "url": ScanInputType.DOMAIN,
    }
    return mapping.get(target_type, ScanInputType.USERNAME)


async def _run_module(
    module_name: str,
    target: str,
    input_type: ScanInputType,
) -> tuple[str, dict]:
    """Run a single SOCMINT module and return (module_name, result_dict)."""
    scanner_name = _SOCMINT_MODULE_MAP.get(module_name)
    if not scanner_name:
        return module_name, {"found": False, "error": f"Unknown module '{module_name}'"}

    registry = get_default_registry()
    scanner = registry.get_by_name(scanner_name)
    if scanner is None:
        return module_name, {
            "found": False,
            "error": f"Scanner '{scanner_name}' not registered",
        }
    if not scanner.supports(input_type):
        return module_name, {
            "found": False,
            "skipped": True,
            "reason": f"Does not support {input_type.value}",
        }

    try:
        result = await scanner.scan(target, input_type)
        return module_name, {
            "found": result.raw_data.get("found", False),
            "data": result.raw_data,
            "error": result.error_message,
            "status": result.status.value,
        }
    except Exception as exc:
        log.warning("socmint module failed", module=module_name, error=str(exc))
        return module_name, {"found": False, "error": str(exc)}


def _default_modules_for_type(target_type: str) -> list[str]:
    if target_type == "email":
        return _DEFAULT_EMAIL_MODULES
    if target_type == "phone":
        return _DEFAULT_PHONE_MODULES
    return _DEFAULT_USERNAME_MODULES


@router.post("/", response_model=SocmintResponse, status_code=status.HTTP_201_CREATED)
async def run_socmint(
    body: SocmintRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocmintResponse:
    input_type = _detect_input_type(body.target_type)
    modules_to_run = body.modules or _default_modules_for_type(body.target_type)

    # Cap concurrency at 5 to avoid overwhelming external services
    semaphore = asyncio.Semaphore(5)

    async def guarded(name: str) -> tuple[str, dict]:
        async with semaphore:
            return await _run_module(name, body.target, input_type)

    pairs = await asyncio.gather(*[guarded(m) for m in modules_to_run])
    results: dict = {name: data for name, data in pairs}

    model = SocmintModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        target=body.target,
        target_type=body.target_type,
        modules_run=modules_to_run,
        results=results,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=SocmintListResponse)
async def list_socmint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SocmintListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(SocmintModel)
            .where(SocmintModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(SocmintModel)
                .where(SocmintModel.owner_id == current_user.id)
                .order_by(SocmintModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )

    return SocmintListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=SocmintResponse)
async def get_socmint(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SocmintResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_socmint(
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
) -> SocmintModel:
    result = await db.execute(
        select(SocmintModel).where(
            SocmintModel.id == scan_id,
            SocmintModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOCMINT scan not found.",
        )
    return model


def _to_response(model: SocmintModel) -> SocmintResponse:
    return SocmintResponse(
        id=model.id,
        target=model.target,
        target_type=model.target_type,
        modules_run=model.modules_run or [],
        results=model.results or {},
        created_at=model.created_at,
    )
