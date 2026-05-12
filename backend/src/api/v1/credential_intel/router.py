"""FastAPI router for the Credential Intelligence module (Domain III, Modules 41-60).

Endpoints:
  POST   /api/v1/credential-intel/      — Run selected modules
  GET    /api/v1/credential-intel/      — Paginated scan history
  GET    /api/v1/credential-intel/{id}  — Single scan result
  DELETE /api/v1/credential-intel/{id}  — Delete scan (204)

Module → scanner mapping (target-type aware):
  email  → breach_hibp (hibp), breach_pwndb (pwndb), breach_h8mail (h8mail), paste_search (paste_sites)
  domain → exposed_git, env_file_miner, domain_squatting, email_spoofing (mx_spf_dmarc),
           malware_match (virustotal), c2_finder (threatfox), exploit_db, ransomware_intel
  ip     → compromised_ip, c2_greynoise (greynoise), malware_match (virustotal)
  hash   → hash_analyzer (password_hash_analyzer)
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

from src.adapters.db.credential_intel_models import CredentialIntelModel
from src.adapters.scanners.registry import get_default_registry
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.credential_intel.schemas import (
    CredentialIntelListResponse,
    CredentialIntelRequest,
    CredentialIntelResponse,
)
from src.core.domain.entities.types import ScanInputType
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()

# Maps frontend module names → registry scanner names + required ScanInputType
_MODULE_REGISTRY_MAP: dict[str, tuple[str, ScanInputType]] = {
    # Breach modules (email targets)
    "breach_hibp":      ("hibp",                   ScanInputType.EMAIL),
    "breach_pwndb":     ("pwndb",                  ScanInputType.EMAIL),
    "breach_h8mail":    ("h8mail",                 ScanInputType.EMAIL),
    "paste_search":     ("paste_sites",            ScanInputType.EMAIL),
    # Hash analysis (hash target, uses DOMAIN as generic string carrier)
    "hash_analyzer":    ("password_hash_analyzer", ScanInputType.DOMAIN),
    # Domain exposure modules
    "exposed_git":      ("exposed_git",            ScanInputType.DOMAIN),
    "env_file_miner":   ("env_file_miner",         ScanInputType.DOMAIN),
    "domain_squatting": ("domain_squatting",       ScanInputType.DOMAIN),
    "email_spoofing":   ("mx_spf_dmarc",           ScanInputType.DOMAIN),
    "malware_match":    ("virustotal",             ScanInputType.DOMAIN),
    "c2_finder":        ("threatfox",              ScanInputType.DOMAIN),
    "exploit_db":       ("exploit_db",             ScanInputType.DOMAIN),
    "ransomware_intel": ("ransomware_intel",       ScanInputType.DOMAIN),
    # IP modules
    "compromised_ip":   ("compromised_ip",         ScanInputType.IP_ADDRESS),
    "c2_greynoise":     ("greynoise",              ScanInputType.IP_ADDRESS),
}

# Default module sets per target type
_DEFAULT_MODULES: dict[str, list[str]] = {
    "email":  ["breach_hibp", "breach_pwndb", "breach_h8mail", "paste_search"],
    "domain": ["exposed_git", "env_file_miner", "domain_squatting", "email_spoofing",
               "malware_match", "c2_finder", "exploit_db", "ransomware_intel"],
    "ip":     ["compromised_ip", "c2_greynoise", "malware_match"],
    "hash":   ["hash_analyzer"],
}


async def _run_module(
    module_name: str,
    target: str,
    target_type: str,
) -> tuple[str, dict]:
    """Execute one credential-intel module and return (name, result_dict)."""
    mapping = _MODULE_REGISTRY_MAP.get(module_name)
    if not mapping:
        return module_name, {"found": False, "error": f"Unknown module '{module_name}'"}

    scanner_name, required_input_type = mapping

    # Hash targets use DOMAIN as a generic string carrier
    if target_type == "hash":
        effective_type = ScanInputType.DOMAIN
    elif target_type == "ip":
        effective_type = ScanInputType.IP_ADDRESS
    elif target_type == "email":
        effective_type = ScanInputType.EMAIL
    else:
        effective_type = ScanInputType.DOMAIN

    # Skip if the module requires a different input type than the effective one
    if effective_type != required_input_type:
        return module_name, {
            "found": False,
            "skipped": True,
            "reason": f"Module requires {required_input_type.value}, target is {target_type}",
        }

    registry = get_default_registry()
    scanner = registry.get_by_name(scanner_name)
    if scanner is None:
        return module_name, {"found": False, "error": f"Scanner '{scanner_name}' not registered"}

    try:
        result = await scanner.scan(target, effective_type)
        return module_name, {
            "found": result.raw_data.get("found", False),
            "data": result.raw_data,
            "error": result.error_message,
            "status": result.status.value,
        }
    except Exception as exc:
        log.warning("credential_intel module failed", module=module_name, error=str(exc))
        return module_name, {"found": False, "error": str(exc)}


@router.post("/", response_model=CredentialIntelResponse, status_code=status.HTTP_201_CREATED)
async def run_credential_intel(
    body: CredentialIntelRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialIntelResponse:
    modules_to_run = body.modules or _DEFAULT_MODULES.get(body.target_type, [])

    semaphore = asyncio.Semaphore(5)

    async def guarded(name: str) -> tuple[str, dict]:
        async with semaphore:
            return await _run_module(name, body.target, body.target_type)

    pairs = await asyncio.gather(*[guarded(m) for m in modules_to_run])
    results: dict = {name: data for name, data in pairs}

    model = CredentialIntelModel(
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


@router.get("/", response_model=CredentialIntelListResponse)
async def list_credential_intel(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CredentialIntelListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(CredentialIntelModel)
            .where(CredentialIntelModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(CredentialIntelModel)
                .where(CredentialIntelModel.owner_id == current_user.id)
                .order_by(CredentialIntelModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return CredentialIntelListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=CredentialIntelResponse)
async def get_credential_intel(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialIntelResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_credential_intel(
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
) -> CredentialIntelModel:
    result = await db.execute(
        select(CredentialIntelModel).where(
            CredentialIntelModel.id == scan_id,
            CredentialIntelModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential intelligence scan not found.",
        )
    return model


def _to_response(model: CredentialIntelModel) -> CredentialIntelResponse:
    return CredentialIntelResponse(
        id=model.id,
        target=model.target,
        target_type=model.target_type,
        modules_run=model.modules_run or [],
        results=model.results or {},
        created_at=model.created_at,
    )
