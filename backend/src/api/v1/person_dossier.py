"""Person dossier generator — aggregates all findings for a person into a structured report.

POST /api/v1/dossier/generate — triggers scanner aggregation and returns structured dossier
GET  /api/v1/dossier/{investigation_id} — retrieves cached dossier for investigation
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(r'\+?[\d\s\-().]{7,20}')
_USERNAME_RE = re.compile(r'(?i)(?:username|handle|alias)[:\s]+([a-zA-Z0-9_.\-]{3,32})')
_LOCATION_RE = re.compile(r'(?i)(?:location|city|country|region)[:\s]+([^,\n]{3,50})')


class DossierRequest(BaseModel):
    investigation_id: str
    subject_name: str | None = None


class PersonDossier(BaseModel):
    investigation_id: str
    subject_name: str | None
    emails: list[str]
    phones: list[str]
    usernames: list[str]
    locations: list[str]
    social_profiles: list[dict[str, Any]]
    employment: list[dict[str, Any]]
    education: list[dict[str, Any]]
    domains_linked: list[str]
    crypto_addresses: list[str]
    data_breach_exposure: list[dict[str, Any]]
    risk_indicators: list[str]
    confidence_score: float
    total_sources: int
    raw_finding_count: int


@router.post("/dossier/generate", response_model=PersonDossier, tags=["dossier"])
async def generate_dossier(
    req: DossierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PersonDossier:
    """Aggregate all scan findings for an investigation into a structured person dossier."""

    # Fetch scan results
    result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == req.investigation_id
        ).limit(200)
    )
    scan_results = result.scalars().all()

    if not scan_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results found for this investigation")

    emails: set[str] = set()
    phones: set[str] = set()
    usernames: set[str] = set()
    locations: set[str] = set()
    social_profiles: list[dict[str, Any]] = []
    employment: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    domains_linked: set[str] = set()
    crypto_addrs: set[str] = set()
    breach_data: list[dict[str, Any]] = []
    risk_indicators: list[str] = []
    sources_seen: set[str] = set()

    for sr in scan_results:
        raw = sr.raw_data or {}
        findings = raw.get("findings", [])
        scanner = sr.scanner_name or ""
        sources_seen.add(scanner)
        raw_text = str(raw)

        # Extract emails
        for e in _EMAIL_RE.findall(raw_text):
            if not e.endswith((".png", ".jpg", ".svg")):
                emails.add(e.lower())

        # Extract phones
        for p in _PHONE_RE.findall(raw_text):
            cleaned = re.sub(r'[\s\-()]', '', p)
            if 7 <= len(cleaned) <= 15:
                phones.add(cleaned)

        # Extract usernames from findings
        for f in findings:
            ftype = f.get("type", "")
            if "username" in ftype or "profile" in ftype or "account" in ftype:
                uname = f.get("username") or f.get("handle") or f.get("account")
                if uname and isinstance(uname, str):
                    usernames.add(uname)
            if "location" in ftype or "geo" in ftype:
                loc = f.get("city") or f.get("country") or f.get("location")
                if loc:
                    locations.add(str(loc))
            if "social" in ftype or "profile" in ftype:
                platform = f.get("platform") or f.get("source") or scanner
                url = f.get("url") or f.get("profile_url") or ""
                if url:
                    social_profiles.append({"platform": platform, "url": url,
                                             "username": f.get("username", "")})
            if "breach" in ftype or "leak" in ftype or "credential" in ftype:
                breach_data.append({
                    "source": f.get("source", scanner),
                    "breach_name": f.get("breach_name") or f.get("source", ""),
                    "records": f.get("total_records") or f.get("count"),
                    "data_types": f.get("data_types", []),
                })
            if "domain" in ftype:
                domain = f.get("domain") or f.get("value")
                if domain and "." in str(domain):
                    domains_linked.add(str(domain))
            if "crypto" in ftype or "wallet" in ftype or "bitcoin" in ftype:
                addr = f.get("address") or f.get("wallet")
                if addr:
                    crypto_addrs.add(str(addr))
            if "employment" in ftype or "job" in ftype or "company" in ftype:
                company = f.get("company") or f.get("employer")
                if company:
                    employment.append({
                        "company": company,
                        "title": f.get("title") or f.get("position", ""),
                        "period": f.get("period") or f.get("dates", ""),
                    })
            sev = f.get("severity", "")
            if sev in ("critical", "high"):
                desc = f.get("description", "")[:100]
                if desc:
                    risk_indicators.append(desc)

    # Deduplicate
    deduped_social = list({s["url"]: s for s in social_profiles if s.get("url")}.values())
    deduped_employment = list({e["company"]: e for e in employment if e.get("company")}.values())

    # Confidence: based on number of corroborating sources
    confidence = min(1.0, len(sources_seen) / 10)

    return PersonDossier(
        investigation_id=req.investigation_id,
        subject_name=req.subject_name,
        emails=sorted(emails)[:20],
        phones=sorted(phones)[:10],
        usernames=sorted(usernames)[:20],
        locations=sorted(locations)[:10],
        social_profiles=deduped_social[:15],
        employment=deduped_employment[:10],
        education=education[:5],
        domains_linked=sorted(domains_linked)[:15],
        crypto_addresses=sorted(crypto_addrs)[:10],
        data_breach_exposure=breach_data[:10],
        risk_indicators=list(set(risk_indicators))[:10],
        confidence_score=round(confidence, 2),
        total_sources=len(sources_seen),
        raw_finding_count=sum(len((sr.raw_data or {}).get("findings", [])) for sr in scan_results),
    )
