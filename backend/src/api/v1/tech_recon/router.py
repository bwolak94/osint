"""FastAPI router for Tech Recon module.

Endpoints:
  POST   /api/v1/tech-recon/      — Run selected modules against a target
  GET    /api/v1/tech-recon/      — Paginated scan history
  GET    /api/v1/tech-recon/{id}  — Single scan result
  DELETE /api/v1/tech-recon/{id}  — Delete scan (204)
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

from src.adapters.db.tech_recon_models import TechReconModel
from src.adapters.scanners.registry import get_default_registry
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.tech_recon.schemas import (
    TechReconListResponse,
    TechReconRequest,
    TechReconResponse,
)
from src.core.domain.entities.types import ScanInputType
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()

# Scanners relevant to technical recon — subset of registry by name
_TECH_RECON_MODULES = [
    # DNS & Subdomains
    "dns_lookup",
    "dns_bruteforce",
    "dnsdumpster",
    "dnsx",
    "subdomain_takeover",
    # Ports & Banners
    "internetdb",
    "banner_grabber",
    # SSL & Security
    "cert_transparency",
    "common_files",
    # WAF & HTTP
    "waf_detect",
    "httpx_probe",
    # BGP & ASN
    "bgp_hijack",
    "asn_lookup",
    "shared_hosting",
    "mx_spf_dmarc",
    "ipv6_mapper",
    # Historical / Cloud
    "traceroute",
    "cloud_assets",
    "wayback",
]


def _detect_target_type(target: str) -> ScanInputType:
    """Heuristically detect whether target is a domain or IP address."""
    import re
    ip_re = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    if ip_re.match(target):
        return ScanInputType.IP_ADDRESS
    return ScanInputType.DOMAIN


async def _run_module(scanner_name: str, target: str, input_type: ScanInputType) -> tuple[str, dict]:
    """Run a single scanner and return (name, result_dict)."""
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
        log.warning("tech_recon module failed", module=scanner_name, error=str(exc))
        return scanner_name, {"found": False, "error": str(exc)}


@router.post("/", response_model=TechReconResponse, status_code=status.HTTP_201_CREATED)
async def run_tech_recon(
    body: TechReconRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TechReconResponse:
    input_type = _detect_target_type(body.target)
    modules_to_run = body.modules if body.modules else _TECH_RECON_MODULES

    # Cap concurrency at 10 parallel scanner calls
    semaphore = asyncio.Semaphore(10)

    async def guarded(name: str) -> tuple[str, dict]:
        async with semaphore:
            return await _run_module(name, body.target, input_type)

    pairs = await asyncio.gather(*[guarded(m) for m in modules_to_run])
    results: dict = {name: data for name, data in pairs}

    model = TechReconModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        target=body.target,
        target_type=input_type.value,
        modules_run=modules_to_run,
        results=results,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=TechReconListResponse)
async def list_tech_recon(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TechReconListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(TechReconModel).where(TechReconModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(TechReconModel)
                .where(TechReconModel.owner_id == current_user.id)
                .order_by(TechReconModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return TechReconListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=TechReconResponse)
async def get_tech_recon(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TechReconResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_tech_recon(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> TechReconModel:
    result = await db.execute(
        select(TechReconModel).where(
            TechReconModel.id == scan_id,
            TechReconModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tech recon scan not found.")
    return model


def _to_response(model: TechReconModel) -> TechReconResponse:
    return TechReconResponse(
        id=model.id,
        target=model.target,
        target_type=model.target_type,
        modules_run=model.modules_run or [],
        results=model.results or {},
        created_at=model.created_at,
    )
