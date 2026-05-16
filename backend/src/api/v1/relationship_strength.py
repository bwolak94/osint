"""Relationship strength scoring for graph entities.

POST /api/v1/graph/relationship-strength/{investigation_id} — score entity relationship strengths
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', re.I)
_IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_DOMAIN_RE = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6}\b')


class EntityRelationship(BaseModel):
    entity_a: str
    entity_b: str
    entity_a_type: str
    entity_b_type: str
    relationship_type: str
    strength: float
    co_occurrences: int
    evidence_sources: list[str]


class RelationshipStrengthResponse(BaseModel):
    investigation_id: str
    total_relationships: int
    strong_relationships: list[EntityRelationship]
    relationship_graph_summary: dict[str, int]


def _entity_type(val: str) -> str:
    if "@" in val:
        return "email"
    if re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', val):
        return "ip"
    if "." in val:
        return "domain"
    return "identifier"


@router.post("/graph/relationship-strength/{investigation_id}",
             response_model=RelationshipStrengthResponse, tags=["graph-relationships"])
async def compute_relationship_strength(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> RelationshipStrengthResponse:
    """Compute relationship strengths between entities in an investigation."""

    result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == investigation_id
        ).limit(200)
    )
    scan_results = result.scalars().all()
    if not scan_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results found")

    # Build co-occurrence matrix: (entity_a, entity_b) -> list of sources
    co_occur: dict[tuple[str, str], list[str]] = defaultdict(list)

    for sr in scan_results:
        findings = (sr.raw_data or {}).get("findings", [])
        for f in findings:
            raw_text = " ".join(str(v) for v in f.values() if isinstance(v, str))
            entities: set[str] = set()

            for email in _EMAIL_RE.findall(raw_text):
                if not email.endswith((".png", ".jpg", ".svg", ".css")):
                    entities.add(email.lower())
            for ip in _IP_RE.findall(raw_text):
                entities.add(ip)

            entity_list = sorted(entities)[:10]
            source = f.get("source") or sr.scanner_name or "unknown"
            for i, ea in enumerate(entity_list):
                for eb in entity_list[i + 1:]:
                    pair = (min(ea, eb), max(ea, eb))
                    co_occur[pair].append(source)

    # Build relationship list
    relationships: list[EntityRelationship] = []
    for (ea, eb), sources in co_occur.items():
        if len(sources) < 1:
            continue
        unique_sources = list(set(sources))
        strength = min(1.0, len(unique_sources) / 5 + len(sources) / 20)
        ea_type = _entity_type(ea)
        eb_type = _entity_type(eb)

        # Determine relationship type
        if ea_type == "email" and eb_type == "domain":
            rel_type = "registered_with"
        elif ea_type == "ip" and eb_type == "domain":
            rel_type = "resolves_to"
        elif ea_type == "email" and eb_type == "ip":
            rel_type = "associated_with"
        else:
            rel_type = "co_occurs_with"

        relationships.append(EntityRelationship(
            entity_a=ea,
            entity_b=eb,
            entity_a_type=ea_type,
            entity_b_type=eb_type,
            relationship_type=rel_type,
            strength=round(strength, 3),
            co_occurrences=len(sources),
            evidence_sources=unique_sources[:5],
        ))

    relationships.sort(key=lambda r: r.strength, reverse=True)
    strong = [r for r in relationships if r.strength >= 0.3]

    # Summary counts
    type_counts: dict[str, int] = defaultdict(int)
    for r in relationships:
        type_counts[r.relationship_type] += 1

    return RelationshipStrengthResponse(
        investigation_id=investigation_id,
        total_relationships=len(relationships),
        strong_relationships=strong[:50],
        relationship_graph_summary=dict(type_counts),
    )
