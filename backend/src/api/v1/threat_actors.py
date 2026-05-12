"""Threat Actor Knowledge Graph API router."""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/threat-actors", tags=["threat-actors"])

# MITRE ATT&CK tactic → technique ID prefix mapping
_TACTIC_MAP: dict[str, list[str]] = {
    "Initial Access": ["T1190", "T1566", "T1078", "T1195"],
    "Execution": ["T1059", "T1203", "T1053"],
    "Persistence": ["T1547", "T1053", "T1078"],
    "Defense Evasion": ["T1027", "T1055", "T1036", "T1562"],
    "Credential Access": ["T1110", "T1621", "T1552"],
    "Discovery": ["T1083", "T1082", "T1057"],
    "Lateral Movement": ["T1534", "T1210", "T1021"],
    "Collection": ["T1040", "T1113", "T1560"],
    "Command & Control": ["T1071", "T1041", "T1095"],
    "Exfiltration": ["T1048", "T1041"],
    "Impact": ["T1485", "T1486", "T1529", "T1561", "T1657"],
}

_MOCK_CAMPAIGNS: dict[str, list[dict]] = {
    "ta-001": [
        {"id": "c-001", "name": "SolarWinds Supply Chain Attack", "year": 2020, "targets": ["Government", "Technology"], "severity": "critical"},
        {"id": "c-002", "name": "NOBELIUM Spear Phishing Wave", "year": 2021, "targets": ["Think Tanks", "NGOs"], "severity": "high"},
    ],
    "ta-002": [
        {"id": "c-003", "name": "Bangladesh Bank Heist", "year": 2016, "targets": ["Financial"], "severity": "critical"},
        {"id": "c-004", "name": "WannaCry Global Ransomware", "year": 2017, "targets": ["Healthcare", "Energy"], "severity": "critical"},
        {"id": "c-005", "name": "AppleJeus Cryptocurrency Theft", "year": 2023, "targets": ["Cryptocurrency"], "severity": "high"},
    ],
    "ta-003": [
        {"id": "c-006", "name": "Fin7 Restaurant PoS Campaign", "year": 2022, "targets": ["Retail", "Hospitality"], "severity": "high"},
    ],
    "ta-004": [
        {"id": "c-007", "name": "NotPetya Destructive Attack", "year": 2017, "targets": ["Energy", "Transportation"], "severity": "critical"},
        {"id": "c-008", "name": "Industroyer Power Grid Attack", "year": 2016, "targets": ["Energy"], "severity": "critical"},
    ],
    "ta-005": [
        {"id": "c-009", "name": "MGM Resorts Social Engineering", "year": 2023, "targets": ["Technology", "Gaming"], "severity": "high"},
    ],
}


class ThreatActor(BaseModel):
    id: str
    name: str
    aliases: list[str]
    origin_country: Optional[str]
    motivation: str  # financial, espionage, hacktivism, sabotage
    sophistication: str  # low, medium, high, nation-state
    active_since: Optional[str]
    last_seen: Optional[str]
    description: str
    ttps: list[str]  # MITRE ATT&CK technique IDs
    targets: list[str]  # sectors/industries
    infrastructure: list[str]  # known IPs, domains, C2s
    malware_families: list[str]
    cve_exploits: list[str]
    ioc_count: int
    source: str  # threatfox, otx, manual
    confidence: float


MOCK_ACTORS: list[ThreatActor] = [
    ThreatActor(
        id="ta-001",
        name="APT29",
        aliases=["Cozy Bear", "The Dukes", "NOBELIUM"],
        origin_country="RU",
        motivation="espionage",
        sophistication="nation-state",
        active_since="2008",
        last_seen="2024",
        description="Russian SVR-linked APT group targeting government and diplomatic entities.",
        ttps=["T1566", "T1190", "T1059", "T1078", "T1547"],
        targets=["Government", "Defense", "Think Tanks", "Healthcare"],
        infrastructure=["185.220.101.x", "cozy-updates.com"],
        malware_families=["MiniDuke", "CosmicDuke", "SUNBURST"],
        cve_exploits=["CVE-2021-26855", "CVE-2020-4006"],
        ioc_count=847,
        source="otx",
        confidence=0.95,
    ),
    ThreatActor(
        id="ta-002",
        name="Lazarus Group",
        aliases=["Hidden Cobra", "ZINC", "Guardians of Peace"],
        origin_country="KP",
        motivation="financial",
        sophistication="nation-state",
        active_since="2009",
        last_seen="2024",
        description="North Korean state-sponsored group known for financial theft and ransomware.",
        ttps=["T1566", "T1059", "T1486", "T1041", "T1027"],
        targets=["Financial", "Cryptocurrency", "Defense", "Energy"],
        infrastructure=["45.142.212.x", "nk-finance.net"],
        malware_families=["WannaCry", "AppleJeus", "BLINDINGCAN"],
        cve_exploits=["CVE-2021-44228", "CVE-2022-0609"],
        ioc_count=1243,
        source="threatfox",
        confidence=0.91,
    ),
    ThreatActor(
        id="ta-003",
        name="FIN7",
        aliases=["Carbanak", "Navigator Group"],
        origin_country="UA",
        motivation="financial",
        sophistication="high",
        active_since="2013",
        last_seen="2024",
        description="Financially motivated criminal group targeting retail and hospitality sectors.",
        ttps=["T1566", "T1059", "T1055", "T1053", "T1071"],
        targets=["Retail", "Hospitality", "Finance", "Healthcare"],
        infrastructure=["fin7-panel.onion", "payment-track.net"],
        malware_families=["Carbanak", "BIRDWATCH", "DICELOADER"],
        cve_exploits=["CVE-2017-11882", "CVE-2018-8174"],
        ioc_count=562,
        source="otx",
        confidence=0.88,
    ),
    ThreatActor(
        id="ta-004",
        name="Sandworm",
        aliases=["Voodoo Bear", "ELECTRUM", "TeleBots"],
        origin_country="RU",
        motivation="sabotage",
        sophistication="nation-state",
        active_since="2009",
        last_seen="2024",
        description="GRU-linked APT responsible for destructive cyberattacks on critical infrastructure.",
        ttps=["T1190", "T1485", "T1529", "T1561", "T1040"],
        targets=["Energy", "Government", "Transportation", "Media"],
        infrastructure=["sandworm-c2.net"],
        malware_families=["NotPetya", "Industroyer", "BlackEnergy", "Cyclops Blink"],
        cve_exploits=["CVE-2022-1040", "CVE-2019-10149"],
        ioc_count=689,
        source="threatfox",
        confidence=0.97,
    ),
    ThreatActor(
        id="ta-005",
        name="Scattered Spider",
        aliases=["UNC3944", "Octo Tempest"],
        origin_country="GB",
        motivation="financial",
        sophistication="high",
        active_since="2022",
        last_seen="2024",
        description="English-speaking cybercriminal group known for social engineering and ransomware.",
        ttps=["T1078", "T1621", "T1534", "T1486", "T1657"],
        targets=["Technology", "Telecommunications", "Finance", "Gaming"],
        infrastructure=["scattered-c2.onion"],
        malware_families=["BlackCat/ALPHV", "Qilin"],
        cve_exploits=[],
        ioc_count=234,
        source="otx",
        confidence=0.82,
    ),
]


class TacticCoverage(BaseModel):
    tactic: str
    techniques: list[str]
    coverage_count: int


class CampaignSummary(BaseModel):
    id: str
    name: str
    year: int
    targets: list[str]
    severity: str


class IOCCategory(BaseModel):
    category: str  # ip, domain, hash, url, email
    count: int
    samples: list[str]


class ThreatActorProfile(BaseModel):
    actor_id: str
    actor_name: str
    generated_at: str
    tactic_coverage: list[TacticCoverage]
    total_tactics_covered: int
    total_techniques: int
    campaigns: list[CampaignSummary]
    ioc_breakdown: list[IOCCategory]
    risk_score: float  # 0-100
    linked_investigation_count: int  # placeholder — in production queries DB


def _categorize_ioc(value: str) -> str:
    if any(c.isalpha() for c in value) and "." in value and not value.startswith("CVE"):
        return "domain"
    parts = value.replace("x", "0").split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return "ip"
    if ".onion" in value:
        return "onion"
    return "other"


def _build_tactic_coverage(ttps: list[str]) -> list[TacticCoverage]:
    result: list[TacticCoverage] = []
    for tactic, prefixes in _TACTIC_MAP.items():
        matched = [t for t in ttps if any(t.startswith(p) for p in prefixes)]
        if matched:
            result.append(TacticCoverage(tactic=tactic, techniques=matched, coverage_count=len(matched)))
    return result


@router.get("/{actor_id}/profile", response_model=ThreatActorProfile)
async def get_threat_actor_profile(actor_id: str) -> ThreatActorProfile:
    """Build a structured profile for a threat actor."""
    actor = next((a for a in MOCK_ACTORS if a.id == actor_id), None)
    if not actor:
        raise HTTPException(status_code=404, detail="Threat actor not found")

    tactic_coverage = _build_tactic_coverage(actor.ttps)

    # IOC breakdown from infrastructure list
    ioc_map: dict[str, list[str]] = {}
    for ioc in actor.infrastructure:
        cat = _categorize_ioc(ioc)
        ioc_map.setdefault(cat, []).append(ioc)
    ioc_breakdown = [
        IOCCategory(category=cat, count=len(vals), samples=vals[:3])
        for cat, vals in ioc_map.items()
    ]

    campaigns = [CampaignSummary(**c) for c in _MOCK_CAMPAIGNS.get(actor_id, [])]

    # Risk score: sophistication × confidence + tactic coverage bonus
    sophistication_weight = {"low": 0.3, "medium": 0.55, "high": 0.75, "nation-state": 1.0}
    base = sophistication_weight.get(actor.sophistication, 0.5) * actor.confidence * 80
    tactic_bonus = min(len(tactic_coverage) * 2, 20)
    risk_score = round(min(base + tactic_bonus, 100), 1)

    return ThreatActorProfile(
        actor_id=actor_id,
        actor_name=actor.name,
        generated_at=datetime.utcnow().isoformat() + "Z",
        tactic_coverage=tactic_coverage,
        total_tactics_covered=len(tactic_coverage),
        total_techniques=len(actor.ttps),
        campaigns=campaigns,
        ioc_breakdown=ioc_breakdown,
        risk_score=risk_score,
        linked_investigation_count=0,
    )


@router.get("/{actor_id}/campaigns", response_model=list[CampaignSummary])
async def get_actor_campaigns(actor_id: str) -> list[CampaignSummary]:
    """Get campaigns associated with a threat actor."""
    if not any(a.id == actor_id for a in MOCK_ACTORS):
        raise HTTPException(status_code=404, detail="Threat actor not found")
    return [CampaignSummary(**c) for c in _MOCK_CAMPAIGNS.get(actor_id, [])]


@router.get("", response_model=list[ThreatActor])
async def list_threat_actors(
    motivation: Optional[str] = Query(None),
    sophistication: Optional[str] = Query(None),
    origin_country: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> list[ThreatActor]:
    """List all threat actors with optional filters."""
    actors = MOCK_ACTORS
    if motivation:
        actors = [a for a in actors if a.motivation == motivation]
    if sophistication:
        actors = [a for a in actors if a.sophistication == sophistication]
    if origin_country:
        actors = [a for a in actors if a.origin_country == origin_country]
    if search:
        s = search.lower()
        actors = [
            a
            for a in actors
            if s in a.name.lower() or any(s in alias.lower() for alias in a.aliases)
        ]
    return actors


@router.get("/{actor_id}", response_model=ThreatActor)
async def get_threat_actor(actor_id: str) -> ThreatActor:
    """Retrieve a single threat actor by ID."""
    for actor in MOCK_ACTORS:
        if actor.id == actor_id:
            return actor
    raise HTTPException(status_code=404, detail="Threat actor not found")
