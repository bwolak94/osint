"""Finding deduplication cleaner — identify and dry-run removal of duplicate findings.

GET  /api/v1/investigations/{id}/duplicates    — find duplicate findings
POST /api/v1/investigations/{id}/deduplicate   — dry-run deduplication report
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["dedup-cleaner"])


class DuplicateGroup(BaseModel):
    content_hash: str
    count: int
    scanner_names: list[str]
    sample_description: str


class DuplicatesResponse(BaseModel):
    investigation_id: str
    total_findings: int
    unique_findings: int
    duplicate_count: int
    duplicate_groups: list[DuplicateGroup]
    estimated_savings_pct: float


def _hash_finding(finding: Any) -> str:
    """Compute MD5 hash of a finding for deduplication."""
    try:
        serialized = json.dumps(finding, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialized = str(finding)
    return hashlib.md5(serialized.encode()).hexdigest()


async def _compute_duplicates(investigation_id: str, db: AsyncSession) -> DuplicatesResponse:
    """Core logic: load scan results for investigation, group by finding hash."""
    try:
        inv_uuid = UUID(investigation_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid investigation ID format") from exc

    inv_result = await db.execute(
        select(InvestigationModel).where(InvestigationModel.id == inv_uuid)
    )
    investigation = inv_result.scalar_one_or_none()
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    scan_results_result = await db.execute(
        select(ScanResultModel).where(ScanResultModel.investigation_id == inv_uuid)
    )
    scan_results = scan_results_result.scalars().all()

    # Build finding-level hash map: hash -> list of (scanner_name, finding)
    hash_map: dict[str, list[tuple[str, Any]]] = {}
    total_findings = 0

    for scan_result in scan_results:
        scanner_name = scan_result.scanner_name or "unknown"
        raw = scan_result.raw_data or {}
        findings = raw.get("findings", []) if isinstance(raw, dict) else []

        for finding in findings:
            total_findings += 1
            h = _hash_finding(finding)
            if h not in hash_map:
                hash_map[h] = []
            hash_map[h].append((scanner_name, finding))

    # Identify groups with more than one occurrence
    duplicate_groups: list[DuplicateGroup] = []
    unique_findings = 0
    duplicate_count = 0

    for content_hash, occurrences in hash_map.items():
        unique_findings += 1
        if len(occurrences) > 1:
            duplicate_count += len(occurrences) - 1
            scanner_names = list({s for s, _ in occurrences})
            sample = occurrences[0][1]
            sample_desc = (
                str(sample.get("description", sample.get("title", str(sample))))[:120]
                if isinstance(sample, dict)
                else str(sample)[:120]
            )
            duplicate_groups.append(DuplicateGroup(
                content_hash=content_hash,
                count=len(occurrences),
                scanner_names=scanner_names,
                sample_description=sample_desc,
            ))

    duplicate_groups.sort(key=lambda g: g.count, reverse=True)

    savings_pct = round(duplicate_count / total_findings * 100, 2) if total_findings > 0 else 0.0

    return DuplicatesResponse(
        investigation_id=investigation_id,
        total_findings=total_findings,
        unique_findings=unique_findings,
        duplicate_count=duplicate_count,
        duplicate_groups=duplicate_groups[:50],  # cap response size
        estimated_savings_pct=savings_pct,
    )


@router.get(
    "/investigations/{investigation_id}/duplicates",
    response_model=DuplicatesResponse,
)
async def find_duplicates(
    investigation_id: str,
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> DuplicatesResponse:
    """Identify duplicate findings within an investigation (read-only analysis)."""
    return await _compute_duplicates(investigation_id, db)


@router.post(
    "/investigations/{investigation_id}/deduplicate",
    response_model=DuplicatesResponse,
)
async def deduplicate_findings(
    investigation_id: str,
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> DuplicatesResponse:
    """Dry-run deduplication: return what would be removed without modifying data."""
    return await _compute_duplicates(investigation_id, db)
