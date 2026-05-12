"""Multi-Investigation Link Analysis — identify shared entities across investigations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SharedEntity(BaseModel):
    entity_type: str
    entity_value: str
    investigation_ids: list[str]
    investigation_titles: list[str]
    occurrence_count: int
    max_confidence: float
    first_seen: str
    last_seen: str
    tags: list[str]


class CrossInvestigationEdge(BaseModel):
    source_investigation_id: str
    target_investigation_id: str
    shared_entity_count: int
    shared_entities: list[str]  # entity values
    link_strength: float  # 0–1 based on Jaccard similarity


class MultiInvestigationGraphResponse(BaseModel):
    investigation_ids: list[str]
    shared_entities: list[SharedEntity]
    cross_investigation_edges: list[CrossInvestigationEdge]
    total_shared: int
    generated_at: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/investigations/multi-graph", response_model=MultiInvestigationGraphResponse)
async def get_multi_investigation_graph(
    investigation_ids: list[str] = Query(..., min_length=2, max_length=10),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    min_occurrences: int = Query(2, ge=2, le=10),
) -> MultiInvestigationGraphResponse:
    """
    Cross-investigation link analysis: find entities shared across ≥2 investigations,
    compute Jaccard similarity between investigation pairs, and return a graph structure.
    """
    from src.adapters.db.models import InvestigationModel, ScanResultModel

    # Verify access and fetch titles
    inv_result = await db.execute(
        select(InvestigationModel).where(
            and_(
                InvestigationModel.id.in_(investigation_ids),
                InvestigationModel.owner_id == current_user.id,
            )
        )
    )
    investigations = {str(i.id): i for i in inv_result.scalars().all()}
    if len(investigations) < 2:
        raise HTTPException(400, "At least 2 accessible investigations are required")

    # Fetch all scan results for the set
    sr_result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id.in_(list(investigations.keys()))
        )
    )
    scan_results = sr_result.scalars().all()

    # Build entity → investigation map
    # Key: (input_type, input_value)   Value: set of inv_ids
    entity_to_invs: dict[tuple[str, str], set[str]] = defaultdict(set)
    entity_meta: dict[tuple[str, str], dict[str, Any]] = {}

    for sr in scan_results:
        if not sr.input_value or not sr.input_type:
            continue
        key = (sr.input_type, sr.input_value)
        entity_to_invs[key].add(str(sr.investigation_id))
        meta = entity_meta.setdefault(key, {
            "max_confidence": 0.0,
            "first_seen": sr.created_at.isoformat() if sr.created_at else "",
            "last_seen": sr.created_at.isoformat() if sr.created_at else "",
        })
        conf = float(getattr(sr, "confidence", 0.5))
        meta["max_confidence"] = max(meta["max_confidence"], conf)
        created_str = sr.created_at.isoformat() if sr.created_at else ""
        if created_str:
            if not meta["first_seen"] or created_str < meta["first_seen"]:
                meta["first_seen"] = created_str
            if created_str > meta["last_seen"]:
                meta["last_seen"] = created_str

    # Filter to entities appearing in ≥ min_occurrences investigations
    shared: list[SharedEntity] = []
    for (etype, evalue), inv_set in entity_to_invs.items():
        if len(inv_set) < min_occurrences:
            continue
        inv_ids = sorted(inv_set)
        meta = entity_meta[(etype, evalue)]
        shared.append(SharedEntity(
            entity_type=etype,
            entity_value=evalue,
            investigation_ids=inv_ids,
            investigation_titles=[investigations[i].title for i in inv_ids if i in investigations],
            occurrence_count=len(inv_ids),
            max_confidence=round(meta["max_confidence"], 3),
            first_seen=meta["first_seen"],
            last_seen=meta["last_seen"],
            tags=[],
        ))

    # Compute cross-investigation edges (Jaccard similarity)
    # Build per-investigation entity sets
    inv_entities: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for (etype, evalue), inv_set in entity_to_invs.items():
        for inv_id in inv_set:
            inv_entities[inv_id].add((etype, evalue))

    edges: list[CrossInvestigationEdge] = []
    inv_list = [i for i in investigation_ids if i in investigations]
    for i in range(len(inv_list)):
        for j in range(i + 1, len(inv_list)):
            a, b = inv_list[i], inv_list[j]
            set_a = inv_entities.get(a, set())
            set_b = inv_entities.get(b, set())
            intersection = set_a & set_b
            union = set_a | set_b
            if not intersection:
                continue
            jaccard = len(intersection) / len(union) if union else 0.0
            edges.append(CrossInvestigationEdge(
                source_investigation_id=a,
                target_investigation_id=b,
                shared_entity_count=len(intersection),
                shared_entities=[v for _, v in list(intersection)[:10]],
                link_strength=round(jaccard, 3),
            ))

    log.info(
        "Multi-investigation graph built",
        investigations=len(investigations),
        shared_entities=len(shared),
        edges=len(edges),
    )

    return MultiInvestigationGraphResponse(
        investigation_ids=list(investigations.keys()),
        shared_entities=sorted(shared, key=lambda e: e.occurrence_count, reverse=True),
        cross_investigation_edges=sorted(edges, key=lambda e: e.link_strength, reverse=True),
        total_shared=len(shared),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
