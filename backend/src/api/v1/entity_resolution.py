"""Entity resolution — deduplicate and normalize entity mentions across findings.

POST /api/v1/entity-resolution/{investigation_id} — resolve entity aliases within investigation
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
_HASH_RE = re.compile(r'\b[a-fA-F0-9]{32}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{64}\b')
_PHONE_RE = re.compile(r'\+\d{7,15}')


class EntityCluster(BaseModel):
    canonical: str
    entity_type: str
    aliases: list[str]
    occurrence_count: int
    severity_max: str
    sources: list[str]
    finding_types: list[str]


class EntityResolutionResponse(BaseModel):
    investigation_id: str
    total_unique_entities: int
    entity_clusters: list[EntityCluster]
    entity_type_counts: dict[str, int]


def _normalize(val: str, etype: str) -> str:
    if etype == "email":
        return val.lower().strip()
    if etype == "ip":
        return val.strip()
    if etype == "domain":
        return val.lower().strip().lstrip("www.").rstrip(".")
    if etype == "hash":
        return val.lower()
    if etype == "phone":
        return re.sub(r'\D', '', val)
    return val.lower().strip()


_SEV_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


@router.post("/entity-resolution/{investigation_id}",
             response_model=EntityResolutionResponse, tags=["entity-resolution"])
async def resolve_entities(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> EntityResolutionResponse:
    """Deduplicate and normalize entity mentions across all findings."""

    result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == investigation_id
        ).limit(200)
    )
    scan_results = result.scalars().all()
    if not scan_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results found")

    # entity_map: canonical -> list of (raw_value, severity, source, finding_type)
    entity_map: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    patterns = [
        ("email", _EMAIL_RE),
        ("ip", _IP_RE),
        ("hash", _HASH_RE),
        ("phone", _PHONE_RE),
    ]

    for sr in scan_results:
        findings = (sr.raw_data or {}).get("findings", [])
        for f in findings:
            sev = f.get("severity", "info")
            src = f.get("source", sr.scanner_name or "")
            ftype = f.get("type", "")
            raw_text = " ".join(str(v) for v in f.values() if isinstance(v, str))

            for etype, pattern in patterns:
                for match in pattern.findall(raw_text):
                    canonical = _normalize(match, etype)
                    if len(canonical) < 3:
                        continue
                    entity_map[(etype, canonical)].append({
                        "raw": match,
                        "severity": sev,
                        "source": src,
                        "finding_type": ftype,
                    })

    # Build clusters
    clusters: list[EntityCluster] = []
    type_counts: dict[str, int] = defaultdict(int)

    for (etype, canonical), occurrences in entity_map.items():
        type_counts[etype] += 1
        aliases = list({o["raw"] for o in occurrences if o["raw"] != canonical})
        sources = list({o["source"] for o in occurrences if o["source"]})
        ftypes = list({o["finding_type"] for o in occurrences if o["finding_type"]})
        max_sev = max(occurrences, key=lambda x: _SEV_ORDER.get(x["severity"], 0))["severity"]
        clusters.append(EntityCluster(
            canonical=canonical,
            entity_type=etype,
            aliases=aliases[:5],
            occurrence_count=len(occurrences),
            severity_max=max_sev,
            sources=sources[:5],
            finding_types=ftypes[:5],
        ))

    clusters.sort(key=lambda c: c.occurrence_count, reverse=True)

    return EntityResolutionResponse(
        investigation_id=investigation_id,
        total_unique_entities=len(clusters),
        entity_clusters=clusters[:100],
        entity_type_counts=dict(type_counts),
    )
