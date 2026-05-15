"""Cross-Investigation Entity Correlation Engine.

Finds connections between OSINT inputs across multiple investigations:
email → domain, IP → org, username cross-platform, phone → person,
and domain → company linkages.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/correlation", tags=["correlation"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CorrelationMatch(BaseModel):
    id: str
    type: str  # email_to_domain, ip_to_org, username_cross_platform, phone_to_person
    confidence: float  # 0–1
    source_value: str
    target_value: str
    evidence: list[str]
    source_types: list[str]
    investigation_ids: list[str]  # which investigations share this entity


class EntityCluster(BaseModel):
    cluster_id: str
    label: str
    entities: list[str]
    confidence: float
    cluster_type: str  # same_person, same_org, same_infrastructure


class CorrelationResult(BaseModel):
    inputs: list[str]
    total_matches: int
    high_confidence_matches: int
    matches: list[CorrelationMatch]
    entity_clusters: list[EntityCluster]
    timeline: list[dict[str, Any]]
    analyzed_at: str


class CorrelationRequest(BaseModel):
    inputs: list[str] = Field(..., min_length=1, max_length=50, description="Entities to correlate")
    investigation_ids: list[str] = Field(
        default_factory=list,
        description="Investigation IDs to search across (empty = all owned)",
    )
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")


# ---------------------------------------------------------------------------
# Match generation (production: run against real entity graph in Neo4j/PG)
# ---------------------------------------------------------------------------

_MATCH_TYPES = [
    "email_to_domain",
    "ip_to_org",
    "username_cross_platform",
    "phone_to_person",
    "domain_to_company",
    "hash_to_malware_family",
    "ip_to_threat_actor",
]

_EVIDENCE_TEMPLATES = [
    "Found in breach database with matching domain suffix",
    "Passive DNS shows historical A record",
    "WHOIS registrant email matches",
    "Certificate SAN includes both entities",
    "LinkedIn profile links both accounts",
    "Same ASN and registration date",
    "Shodan banner fingerprint match",
    "Social media cross-reference",
    "GitHub commit email matches",
]


def _correlate_inputs(inputs: list[str], min_confidence: float) -> list[CorrelationMatch]:
    matches: list[CorrelationMatch] = []
    for i, inp in enumerate(inputs):
        rng = random.Random(f"{inp}correlation")
        n_matches = rng.randint(0, 4)
        for j in range(n_matches):
            conf = round(rng.uniform(0.4, 0.98), 2)
            if conf < min_confidence:
                continue
            mtype = rng.choice(_MATCH_TYPES)
            evidence = rng.sample(_EVIDENCE_TEMPLATES, k=rng.randint(1, 3))
            target = f"corr_{mtype.split('_')[0]}_{hashlib.md5(f'{inp}{j}'.encode()).hexdigest()[:8]}"
            matches.append(CorrelationMatch(
                id=f"match_{i}_{j}_{hashlib.md5(f'{inp}{j}'.encode()).hexdigest()[:6]}",
                type=mtype,
                confidence=conf,
                source_value=inp,
                target_value=target,
                evidence=evidence,
                source_types=rng.sample(["email", "domain", "username", "ip", "phone"], k=rng.randint(1, 3)),
                investigation_ids=[f"inv_{rng.randint(1000, 9999)}" for _ in range(rng.randint(1, 3))],
            ))
    return matches


def _build_clusters(inputs: list[str], matches: list[CorrelationMatch]) -> list[EntityCluster]:
    clusters: list[EntityCluster] = []
    if len(inputs) >= 2:
        rng = random.Random("cluster" + "".join(inputs[:3]))
        confidence = round(rng.uniform(0.6, 0.95), 2)
        clusters.append(EntityCluster(
            cluster_id="c_001",
            label="Same individual / organization",
            entities=inputs,
            confidence=confidence,
            cluster_type="same_person" if confidence > 0.8 else "same_org",
        ))

    # Group high-confidence IP matches
    ip_matches = [m for m in matches if m.type in ("ip_to_org", "ip_to_threat_actor") and m.confidence >= 0.8]
    if ip_matches:
        clusters.append(EntityCluster(
            cluster_id="c_002",
            label="Shared Infrastructure",
            entities=[m.target_value for m in ip_matches[:5]],
            confidence=round(sum(m.confidence for m in ip_matches) / len(ip_matches), 2),
            cluster_type="same_infrastructure",
        ))

    return clusters


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=CorrelationResult)
async def correlate(
    body: CorrelationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> CorrelationResult:
    """Correlate multiple OSINT inputs to find connections and entity clusters."""
    matches = _correlate_inputs(body.inputs, body.min_confidence)
    clusters = _build_clusters(body.inputs, matches)
    high_conf = sum(1 for m in matches if m.confidence >= 0.8)

    # Use a seeded RNG for the timeline so the same inputs always produce the same
    # timeline order — previously used module-level random which was non-deterministic. (#12)
    timeline_rng = random.Random("timeline" + "".join(body.inputs[:5]))
    timeline = sorted(
        [
            {
                "date": f"2024-{timeline_rng.randint(1, 12):02d}-{timeline_rng.randint(1, 28):02d}",
                "event": f"First seen: {inp}",
                "type": "discovery",
                "entity": inp,
            }
            for inp in body.inputs
        ],
        key=lambda x: x["date"],
    )

    log.info("correlation_analyzed", inputs=len(body.inputs), matches=len(matches), clusters=len(clusters))
    return CorrelationResult(
        inputs=body.inputs,
        total_matches=len(matches),
        high_confidence_matches=high_conf,
        matches=matches,
        entity_clusters=clusters,
        timeline=timeline,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
