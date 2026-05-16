"""IP reputation aggregator — multi-source IP reputation check.

POST /api/v1/ip-reputation/check — check IP(s) against multiple reputation sources
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_IP_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')


class IPReputationRequest(BaseModel):
    ips: list[str]

    class Config:
        json_schema_extra = {"example": {"ips": ["8.8.8.8", "1.1.1.1"]}}


class IPReputationResult(BaseModel):
    ip: str
    is_malicious: bool
    abuse_score: int | None
    country: str | None
    org: str | None
    is_tor: bool
    is_vpn: bool
    open_ports: list[int]
    cves: list[str]
    sources: list[str]
    overall_risk: str


class IPReputationResponse(BaseModel):
    results: list[IPReputationResult]
    total_malicious: int
    total_clean: int


@router.post("/ip-reputation/check", response_model=IPReputationResponse,
             tags=["ip-reputation"])
async def check_ip_reputation(
    req: IPReputationRequest,
    current_user: UserModel = Depends(get_current_user),
) -> IPReputationResponse:
    """Check IP reputation across AbuseIPDB, Shodan InternetDB, and ip-api."""
    ips = [ip.strip() for ip in req.ips if _IP_RE.match(ip.strip())][:20]
    if not ips:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No valid IPs provided")

    results: list[IPReputationResult] = []

    async with httpx.AsyncClient(
        timeout=8,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; IPReputationScanner/1.0)"},
    ) as client:
        semaphore = asyncio.Semaphore(5)

        async def check_ip(ip: str) -> None:
            async with semaphore:
                is_malicious = False
                abuse_score: int | None = None
                country: str | None = None
                org: str | None = None
                is_tor = False
                is_vpn = False
                open_ports: list[int] = []
                cves: list[str] = []
                sources: list[str] = []

                # 1. Shodan InternetDB (no API key)
                try:
                    resp = await client.get(f"https://internetdb.shodan.io/{ip}", timeout=5)
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text)
                        open_ports = data.get("ports", [])
                        cves = data.get("vulns", [])[:10]
                        tags = data.get("tags", [])
                        is_tor = "tor" in [t.lower() for t in tags]
                        is_vpn = any(t.lower() in ("vpn", "proxy") for t in tags)
                        if cves:
                            is_malicious = True
                        sources.append("shodan")
                except Exception:
                    pass

                # 2. ip-api.com (free, no key)
                try:
                    resp = await client.get(
                        f"http://ip-api.com/json/{ip}?fields=country,org,proxy,hosting",
                        timeout=5,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text)
                        country = data.get("country")
                        org = data.get("org")
                        if data.get("proxy") or data.get("hosting"):
                            is_vpn = True
                        sources.append("ip-api")
                except Exception:
                    pass

                # 3. AbuseIPDB public check (limited, no key)
                try:
                    resp = await client.get(
                        f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90",
                        headers={"Key": "", "Accept": "application/json"},
                        timeout=5,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text).get("data", {})
                        abuse_score = data.get("abuseConfidenceScore")
                        if abuse_score and abuse_score > 25:
                            is_malicious = True
                        sources.append("abuseipdb")
                except Exception:
                    pass

                risk = "critical" if (is_malicious and cves) else ("high" if is_malicious else ("medium" if is_vpn or is_tor else "low"))

                results.append(IPReputationResult(
                    ip=ip,
                    is_malicious=is_malicious,
                    abuse_score=abuse_score,
                    country=country,
                    org=org,
                    is_tor=is_tor,
                    is_vpn=is_vpn,
                    open_ports=open_ports[:10],
                    cves=cves[:5],
                    sources=sources,
                    overall_risk=risk,
                ))

        await asyncio.gather(*[check_ip(ip) for ip in ips])

    malicious_count = sum(1 for r in results if r.is_malicious)
    return IPReputationResponse(
        results=results,
        total_malicious=malicious_count,
        total_clean=len(results) - malicious_count,
    )
