"""Threat Actor Knowledge Graph API router."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/threat-actors", tags=["threat-actors"])


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
