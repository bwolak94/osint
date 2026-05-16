"""WHOIS pivot — pivot from a domain to all domains registered by same registrant.

POST /api/v1/whois-pivot — find all domains linked to a registrant email/org/nameserver
"""

from __future__ import annotations

import asyncio
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


class WhoisPivotRequest(BaseModel):
    query: str
    pivot_type: str = "email"  # email | org | nameserver | registrar


class WhoisPivotResult(BaseModel):
    query: str
    pivot_type: str
    related_domains: list[str]
    total_found: int
    sources: list[str]
    risk_indicators: list[str]


@router.post("/whois-pivot", response_model=WhoisPivotResult, tags=["whois-pivot"])
async def whois_pivot(
    req: WhoisPivotRequest,
    current_user: UserModel = Depends(get_current_user),
) -> WhoisPivotResult:
    """Pivot from a registrant email/org/nameserver to find all related domains."""
    related_domains: set[str] = set()
    sources: list[str] = []
    risk_indicators: list[str] = []

    async with httpx.AsyncClient(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; WhoisPivotScanner/1.0)"},
    ) as client:
        # 1. ViewDNS.info reverse WHOIS
        try:
            from urllib.parse import quote
            resp = await client.get(
                f"https://viewdns.info/reversewhois/?q={quote(req.query)}&l=500&t=&apikey=",
                headers={"Accept": "text/html"},
                timeout=8,
            )
            if resp.status_code == 200:
                import re
                # Extract domain names from table
                domain_matches = re.findall(
                    r'<td>([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})</td>',
                    resp.text,
                )
                for d in domain_matches[:100]:
                    if "." in d and len(d) > 3:
                        related_domains.add(d.lower())
                if domain_matches:
                    sources.append("ViewDNS")
        except Exception as exc:
            log.debug("ViewDNS reverse WHOIS error", error=str(exc))

        # 2. WhoisXML API (free tier)
        try:
            resp = await client.get(
                f"https://reverse-whois.whoisxmlapi.com/api/v2?apiKey=&basicSearchTerms={req.query}&mode=purchase",
                timeout=8,
            )
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                domains = data.get("domainsList", [])
                for d in domains[:200]:
                    related_domains.add(d.lower())
                if domains:
                    sources.append("WhoisXML")
        except Exception as exc:
            log.debug("WhoisXML error", error=str(exc))

        # 3. SecurityTrails (free tier probe)
        try:
            from urllib.parse import quote
            resp = await client.get(
                f"https://api.securitytrails.com/v1/domains/list?apikey=&filter[whois_{req.pivot_type}]={quote(req.query)}",
                timeout=8,
            )
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                for d in data.get("records", [])[:200]:
                    hostname = d.get("hostname", "")
                    if hostname:
                        related_domains.add(hostname.lower())
                if data.get("records"):
                    sources.append("SecurityTrails")
        except Exception as exc:
            log.debug("SecurityTrails error", error=str(exc))

    # Risk indicators
    if len(related_domains) > 50:
        risk_indicators.append("high_domain_volume: registrant controls many domains")
    suspicious_tlds = [d for d in related_domains if d.endswith(
        (".xyz", ".top", ".click", ".work", ".loan", ".win", ".bid", ".racing")
    )]
    if suspicious_tlds:
        risk_indicators.append(f"suspicious_tlds: {len(suspicious_tlds)} domains with high-risk TLDs")

    return WhoisPivotResult(
        query=req.query,
        pivot_type=req.pivot_type,
        related_domains=sorted(related_domains)[:200],
        total_found=len(related_domains),
        sources=sources,
        risk_indicators=risk_indicators,
    )
