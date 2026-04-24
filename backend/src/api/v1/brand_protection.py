from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
import hashlib
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/brand-protection", tags=["brand-protection"])

class BrandThreat(BaseModel):
    id: str
    type: str  # typosquat, phishing_site, fake_social, counterfeit_app, impersonation
    target: str
    threat_value: str
    risk_level: str
    first_detected: str
    status: str  # active, taken_down, monitoring
    registrar: Optional[str]
    hosting_ip: Optional[str]
    description: str

class BrandProtectionResult(BaseModel):
    brand: str
    total_threats: int
    critical_threats: int
    active_threats: int
    taken_down: int
    threats: list[BrandThreat]
    monitored_domains: list[str]
    last_scan: str

@router.get("/scan", response_model=BrandProtectionResult)
async def scan_brand(brand: str):
    """Scan for brand impersonation and typosquat threats"""
    threat_types = ["typosquat", "phishing_site", "fake_social", "counterfeit_app", "impersonation"]
    risk_levels = ["critical", "high", "medium", "low"]
    statuses = ["active", "active", "active", "monitoring", "taken_down"]

    threats = []
    for i in range(random.randint(3, 12)):
        ttype = random.choice(threat_types)
        threat_val = (
            f"{brand.lower()}-secure.com" if ttype == "typosquat" else
            f"@{brand.lower()}_official_help" if ttype == "fake_social" else
            f"phishing.{brand.lower()}.fake.com" if ttype == "phishing_site" else
            f"{brand.lower()} Official App (fake)" if ttype == "counterfeit_app" else
            f"CEO {brand} (impersonator)"
        )
        days_ago = random.randint(1, 90)
        threats.append(BrandThreat(
            id=f"threat_{i}_{hashlib.md5(threat_val.encode()).hexdigest()[:6]}",
            type=ttype,
            target=brand,
            threat_value=threat_val,
            risk_level=random.choice(risk_levels),
            first_detected=(datetime.utcnow() - timedelta(days=days_ago)).isoformat(),
            status=random.choice(statuses),
            registrar=random.choice(["GoDaddy", "Namecheap", "Cloudflare", None]) if ttype in ("typosquat", "phishing_site") else None,
            hosting_ip=f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}" if ttype in ("typosquat", "phishing_site") else None,
            description=f"Detected {ttype.replace('_', ' ')} targeting {brand} brand"
        ))

    return BrandProtectionResult(
        brand=brand,
        total_threats=len(threats),
        critical_threats=sum(1 for t in threats if t.risk_level == "critical"),
        active_threats=sum(1 for t in threats if t.status == "active"),
        taken_down=sum(1 for t in threats if t.status == "taken_down"),
        threats=threats,
        monitored_domains=[f"{brand.lower()}.com", f"{brand.lower()}.net", f"{brand.lower()}.org"],
        last_scan=datetime.utcnow().isoformat()
    )
