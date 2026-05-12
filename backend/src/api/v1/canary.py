from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/canary", tags=["canary"])

_tokens: dict[str, dict] = {}
_alerts: list[dict] = []

class CanaryToken(BaseModel):
    id: str
    name: str
    type: str  # web_bug, dns, aws_key, word_doc, pdf, email, http
    token_url: str
    status: str  # active, triggered, disabled
    trigger_count: int
    last_triggered: Optional[str]
    deployment_notes: str
    tags: list[str]
    created_at: str

class CanaryAlert(BaseModel):
    id: str
    token_id: str
    token_name: str
    triggered_at: str
    source_ip: str
    user_agent: Optional[str]
    geo_location: Optional[str]
    additional_data: dict

class CreateTokenInput(BaseModel):
    name: str
    type: str
    deployment_notes: str = ""
    tags: list[str] = []

@router.get("/tokens", response_model=list[CanaryToken])
async def list_tokens():
    return [CanaryToken(**t) for t in _tokens.values()]

@router.post("/tokens", response_model=CanaryToken)
async def create_token(data: CreateTokenInput):
    tid = str(uuid.uuid4())
    token_id = uuid.uuid4().hex[:16]
    base = "https://canarytokens.example.com"
    urls = {
        "web_bug": f"{base}/pixel/{token_id}.png",
        "dns": f"{token_id}.dns.canarytokens.example.com",
        "aws_key": f"AKIA{token_id[:16].upper()}",
        "word_doc": f"{base}/download/{token_id}.docx",
        "pdf": f"{base}/download/{token_id}.pdf",
        "email": f"canary-{token_id}@canarytokens.example.com",
        "http": f"{base}/t/{token_id}"
    }
    now = datetime.utcnow().isoformat()
    token = {
        "id": tid, "name": data.name, "type": data.type,
        "token_url": urls.get(data.type, f"{base}/t/{token_id}"),
        "status": "active", "trigger_count": 0, "last_triggered": None,
        "deployment_notes": data.deployment_notes, "tags": data.tags, "created_at": now
    }
    _tokens[tid] = token
    return CanaryToken(**token)

@router.post("/tokens/{token_id}/trigger")
async def simulate_trigger(token_id: str):
    """Simulate a token being triggered (for testing)"""
    if token_id not in _tokens:
        raise HTTPException(status_code=404, detail="Token not found")
    token = _tokens[token_id]
    now = datetime.utcnow().isoformat()
    token["trigger_count"] += 1
    token["last_triggered"] = now
    token["status"] = "triggered"

    alert = {
        "id": str(uuid.uuid4()), "token_id": token_id, "token_name": token["name"],
        "triggered_at": now,
        "source_ip": f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "geo_location": random.choice(["Bucharest, RO", "Moscow, RU", "Beijing, CN", "Unknown"]),
        "additional_data": {"referer": "https://suspicious-site.com"}
    }
    _alerts.append(alert)
    return {"triggered": True, "alert": alert}

@router.get("/alerts", response_model=list[CanaryAlert])
async def list_alerts():
    return [CanaryAlert(**a) for a in _alerts]
