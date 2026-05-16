"""Job posting intelligence scanner — infer tech stack and plans from job ads.

Finds:
- Open job postings on LinkedIn, Indeed, Glassdoor, Greenhouse, Lever
- Technology stack from job requirements (infer infra, security tools, cloud)
- Growth signals (number of open roles, role types)
- Planned hiring areas (security, cloud, AI, compliance)
- Salary ranges where disclosed
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Tech stack keywords to extract from job descriptions
_TECH_PATTERNS: dict[str, list[str]] = {
    "cloud": ["AWS", "Azure", "GCP", "Google Cloud", "Kubernetes", "Docker", "Terraform"],
    "languages": ["Python", "Go", "Rust", "Java", "Node.js", "TypeScript", "Ruby", "Scala"],
    "databases": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra", "DynamoDB"],
    "security": ["SIEM", "SOC", "SAST", "DAST", "Splunk", "CrowdStrike", "Okta", "Palo Alto"],
    "ml_ai": ["TensorFlow", "PyTorch", "LLM", "OpenAI", "machine learning", "NLP", "RAG"],
    "monitoring": ["Datadog", "Prometheus", "Grafana", "New Relic", "PagerDuty", "Jaeger"],
}


class JobIntelScanner(BaseOsintScanner):
    """Job posting intelligence scanner for tech stack inference."""

    scanner_name = "job_intel"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL})
    cache_ttl = 43200
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        tech_stack: dict[str, list[str]] = {}

        company = query.split(".")[0].replace("-", " ") if "." in query else query
        if "@" in company:
            company = company.split("@")[1].split(".")[0]

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            semaphore = asyncio.Semaphore(3)

            async def search_greenhouse() -> None:
                async with semaphore:
                    try:
                        # Greenhouse public job board API
                        resp = await client.get(
                            f"https://api.greenhouse.io/v1/boards/{company.lower().replace(' ', '')}/jobs",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            jobs = data.get("jobs", [])
                            if jobs:
                                all_text = " ".join(
                                    j.get("title", "") + " " + j.get("content", "")
                                    for j in jobs[:20]
                                )
                                found_tech = _extract_tech(all_text)
                                tech_stack.update(found_tech)

                                departments = list({j.get("departments", [{}])[0].get("name", "")
                                                   for j in jobs if j.get("departments")})
                                identifiers.append("info:job_intel:greenhouse")
                                findings.append({
                                    "type": "job_postings_found",
                                    "severity": "info",
                                    "source": "Greenhouse",
                                    "company": company,
                                    "total_openings": len(jobs),
                                    "departments": departments[:8],
                                    "tech_signals": found_tech,
                                    "description": f"Greenhouse: {len(jobs)} open roles at {company} — tech: {_tech_summary(found_tech)}",
                                })
                    except Exception as exc:
                        log.debug("Greenhouse error", error=str(exc))

            async def search_lever() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://api.lever.co/v0/postings/{company.lower().replace(' ', '')}?mode=json",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            if isinstance(data, list) and data:
                                all_text = " ".join(
                                    j.get("text", "") + " " + " ".join(
                                        l.get("content", "") for l in j.get("lists", [])
                                    )
                                    for j in data[:20]
                                )
                                found_tech = _extract_tech(all_text)
                                tech_stack.update(found_tech)
                                identifiers.append("info:job_intel:lever")
                                findings.append({
                                    "type": "job_postings_found",
                                    "severity": "info",
                                    "source": "Lever",
                                    "company": company,
                                    "total_openings": len(data),
                                    "tech_signals": found_tech,
                                    "description": f"Lever: {len(data)} open roles at {company} — tech: {_tech_summary(found_tech)}",
                                })
                    except Exception as exc:
                        log.debug("Lever error", error=str(exc))

            async def search_indeed() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://www.indeed.com/jobs?q={quote(company)}&sort=date",
                            headers={"Accept": "text/html"},
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            count_match = re.search(r'([\d,]+)\s+job', body, re.I)
                            count = int(count_match.group(1).replace(",", "")) if count_match else None
                            found_tech = _extract_tech(body[:20000])
                            if count or found_tech:
                                tech_stack.update(found_tech)
                                identifiers.append("info:job_intel:indeed")
                                findings.append({
                                    "type": "job_postings_found",
                                    "severity": "info",
                                    "source": "Indeed",
                                    "company": company,
                                    "total_openings": count,
                                    "tech_signals": found_tech,
                                    "url": f"https://www.indeed.com/jobs?q={quote(company)}",
                                    "description": f"Indeed: {count or '?'} jobs for {company}",
                                })
                    except Exception as exc:
                        log.debug("Indeed error", error=str(exc))

            await asyncio.gather(search_greenhouse(), search_lever(), search_indeed())

        if tech_stack:
            findings.append({
                "type": "inferred_tech_stack",
                "severity": "info",
                "source": "Job Intel",
                "company": company,
                "tech_stack": tech_stack,
                "description": f"Inferred tech stack from job postings: {_tech_summary(tech_stack)}",
            })

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "company": company,
            "tech_stack": tech_stack,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_tech(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for category, keywords in _TECH_PATTERNS.items():
        matched = [kw for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', text, re.I)]
        if matched:
            found[category] = matched
    return found


def _tech_summary(tech: dict[str, list[str]]) -> str:
    all_tech = [item for items in tech.values() for item in items[:2]]
    return ", ".join(all_tech[:6]) or "none detected"
