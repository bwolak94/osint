from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import uuid, random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/threat-feed", tags=["threat-feed"])

_feeds: dict[str, dict] = {}

class ThreatIndicator(BaseModel):
    id: str
    type: str  # ip, domain, hash, url, email
    value: str
    confidence: int  # 0-100
    severity: str
    tags: list[str]
    first_seen: str
    last_seen: str
    ttl_days: int
    tlp: str  # WHITE, GREEN, AMBER, RED

class ThreatFeed(BaseModel):
    id: str
    name: str
    description: str
    format: str  # STIX, MISP, CSV, JSON
    status: str
    indicator_count: int
    subscribers: int
    last_updated: str
    indicators: list[ThreatIndicator]

class CreateFeedInput(BaseModel):
    name: str
    description: str
    format: str = "JSON"
    tlp: str = "AMBER"

def _make_indicator(feed_id: str) -> ThreatIndicator:
    types = ["ip", "domain", "hash", "url", "email"]
    itype = random.choice(types)
    vals = {
        "ip": f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
        "domain": f"malicious-{random.randint(1000,9999)}.evil.com",
        "hash": f"{''.join([f'{random.randint(0,15):x}' for _ in range(64)])}",
        "url": f"http://phish-{random.randint(100,999)}.example.com/payload",
        "email": f"attacker{random.randint(1,99)}@malicious.com"
    }
    return ThreatIndicator(
        id=str(uuid.uuid4()), type=itype, value=vals[itype],
        confidence=random.randint(60, 99), severity=random.choice(["critical", "high", "medium"]),
        tags=random.sample(["apt", "ransomware", "phishing", "c2", "exploit"], random.randint(1, 3)),
        first_seen=(datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
        last_seen=datetime.utcnow().isoformat(), ttl_days=random.choice([7, 14, 30, 90]),
        tlp=random.choice(["WHITE", "GREEN", "AMBER"])
    )

@router.get("/feeds", response_model=list[ThreatFeed])
async def list_feeds():
    return [ThreatFeed(**f) for f in _feeds.values()]

@router.post("/feeds", response_model=ThreatFeed)
async def create_feed(data: CreateFeedInput):
    fid = str(uuid.uuid4())
    indicators = [_make_indicator(fid) for _ in range(random.randint(5, 15))]
    feed = {
        "id": fid, "name": data.name, "description": data.description,
        "format": data.format, "status": "active",
        "indicator_count": len(indicators), "subscribers": 0,
        "last_updated": datetime.utcnow().isoformat(),
        "indicators": [i.model_dump() for i in indicators]
    }
    _feeds[fid] = feed
    return ThreatFeed(**feed)

@router.get("/feeds/{feed_id}/export")
async def export_feed(feed_id: str, format: str = "json"):
    if feed_id not in _feeds:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Feed not found")
    feed = _feeds[feed_id]
    indicators = [ThreatIndicator(**i) for i in feed["indicators"]]
    if format == "csv":
        lines = ["type,value,confidence,severity,tlp,tags"]
        for i in indicators:
            lines.append(f"{i.type},{i.value},{i.confidence},{i.severity},{i.tlp},{';'.join(i.tags)}")
        return {"content": "\n".join(lines), "format": "csv"}
    return {"indicators": [i.model_dump() for i in indicators], "format": "json", "feed_name": feed["name"]}
