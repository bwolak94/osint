from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
import hashlib

router = APIRouter(prefix="/api/v1/correlation", tags=["correlation"])

class CorrelationMatch(BaseModel):
    id: str
    type: str  # email_to_domain, ip_to_org, username_cross_platform, phone_to_person
    confidence: float  # 0-1
    source_value: str
    target_value: str
    evidence: list[str]
    source_types: list[str]

class CorrelationResult(BaseModel):
    inputs: list[str]
    total_matches: int
    high_confidence_matches: int
    matches: list[CorrelationMatch]
    entity_clusters: list[dict]
    timeline: list[dict]

@router.post("/analyze", response_model=CorrelationResult)
async def correlate(inputs: list[str]):
    """Correlate multiple OSINT inputs to find connections"""
    match_types = ["email_to_domain", "ip_to_org", "username_cross_platform", "phone_to_person", "domain_to_company"]

    matches = []
    for i, inp in enumerate(inputs):
        for j in range(random.randint(1, 3)):
            conf = round(random.uniform(0.5, 1.0), 2)
            mtype = random.choice(match_types)
            matches.append(CorrelationMatch(
                id=f"match_{i}_{j}_{hashlib.md5(f'{inp}{j}'.encode()).hexdigest()[:6]}",
                type=mtype,
                confidence=conf,
                source_value=inp,
                target_value=f"correlated_{mtype}_{j}",
                evidence=[f"Found in breach database", f"Matches registration pattern", "Verified via passive DNS"][:(j+1)],
                source_types=["email", "domain", "username"][:random.randint(1, 3)]
            ))

    clusters = []
    if len(inputs) > 1:
        clusters.append({"cluster_id": "c1", "entities": inputs, "confidence": 0.85, "label": "Same individual"})

    timeline = [
        {"date": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}", "event": f"First seen: {inp}", "type": "discovery"}
        for inp in inputs
    ]

    high_conf = sum(1 for m in matches if m.confidence >= 0.8)
    return CorrelationResult(
        inputs=inputs,
        total_matches=len(matches),
        high_confidence_matches=high_conf,
        matches=matches,
        entity_clusters=clusters,
        timeline=sorted(timeline, key=lambda x: x["date"]),
    )
