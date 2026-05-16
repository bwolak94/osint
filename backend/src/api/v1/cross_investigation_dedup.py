"""Cross-investigation deduplication — find overlapping entities across investigations.

GET /api/v1/investigations/dedup/overlaps — find shared entities between user's investigations
POST /api/v1/investigations/dedup/merge-suggestions — suggest which investigations to merge
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_EMAIL_RE = re.compile(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}')
_IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_DOMAIN_RE = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b')
_HASH_RE = re.compile(r'\b[a-fA-F0-9]{32,64}\b')


class OverlapEntry(BaseModel):
    entity: str
    entity_type: str
    investigation_ids: list[str]
    investigation_titles: list[str]
    occurrence_count: int


class MergeSuggestion(BaseModel):
    investigation_ids: list[str]
    titles: list[str]
    shared_entities: list[str]
    overlap_score: float
    reason: str


class DedupResponse(BaseModel):
    total_overlaps: int
    overlapping_entities: list[OverlapEntry]
    merge_suggestions: list[MergeSuggestion]


def _extract_entities(text: str) -> dict[str, set[str]]:
    return {
        "email": set(e.lower() for e in _EMAIL_RE.findall(text)),
        "ip": set(_IP_RE.findall(text)),
        "hash": set(h.lower() for h in _HASH_RE.findall(text) if len(h) in (32, 40, 64)),
    }


@router.get("/investigations/dedup/overlaps", response_model=DedupResponse, tags=["dedup"])
async def find_overlaps(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> DedupResponse:
    """Find overlapping entities across all investigations for the current user."""

    # Fetch all investigations for this user
    inv_result = await db.execute(
        select(InvestigationModel).where(
            InvestigationModel.owner_id == current_user.id
        ).limit(50)
    )
    investigations = inv_result.scalars().all()

    if len(investigations) < 2:
        return DedupResponse(total_overlaps=0, overlapping_entities=[], merge_suggestions=[])

    inv_map: dict[str, InvestigationModel] = {str(inv.id): inv for inv in investigations}

    # Fetch scan results per investigation
    inv_entities: dict[str, dict[str, set[str]]] = {}
    for inv in investigations:
        sr_result = await db.execute(
            select(ScanResultModel).where(
                ScanResultModel.investigation_id == inv.id
            ).limit(50)
        )
        scan_results = sr_result.scalars().all()
        combined_text = " ".join(str(sr.raw_data or {}) for sr in scan_results)
        inv_entities[str(inv.id)] = _extract_entities(combined_text)

    # Find entities appearing in multiple investigations
    entity_to_invs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for inv_id, entities in inv_entities.items():
        for etype, vals in entities.items():
            for val in vals:
                entity_to_invs[(etype, val)].add(inv_id)

    overlaps: list[OverlapEntry] = []
    for (etype, val), inv_ids in entity_to_invs.items():
        if len(inv_ids) >= 2:
            overlaps.append(OverlapEntry(
                entity=val,
                entity_type=etype,
                investigation_ids=list(inv_ids),
                investigation_titles=[
                    getattr(inv_map.get(i), "title", i) for i in inv_ids
                ],
                occurrence_count=len(inv_ids),
            ))

    overlaps.sort(key=lambda x: x.occurrence_count, reverse=True)

    # Generate merge suggestions — investigations sharing ≥3 entities
    inv_pair_shared: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (etype, val), inv_ids in entity_to_invs.items():
        if len(inv_ids) == 2:
            pair = tuple(sorted(inv_ids))
            inv_pair_shared[pair].append(val)  # type: ignore[arg-type]

    merge_suggestions: list[MergeSuggestion] = []
    for (id1, id2), shared in inv_pair_shared.items():
        if len(shared) >= 3:
            overlap_score = min(1.0, len(shared) / 10)
            merge_suggestions.append(MergeSuggestion(
                investigation_ids=[id1, id2],
                titles=[
                    getattr(inv_map.get(id1), "title", id1),
                    getattr(inv_map.get(id2), "title", id2),
                ],
                shared_entities=shared[:10],
                overlap_score=round(overlap_score, 2),
                reason=f"Share {len(shared)} common entities ({', '.join(shared[:3])}...)",
            ))

    merge_suggestions.sort(key=lambda x: x.overlap_score, reverse=True)

    return DedupResponse(
        total_overlaps=len(overlaps),
        overlapping_entities=overlaps[:50],
        merge_suggestions=merge_suggestions[:10],
    )
