"""Court records OSINT scanner — CourtListener, PACER public dockets, state courts.

Searches:
- CourtListener (free) — federal court opinions, dockets, PACER mirroring
- PACER (public case lookup) — federal civil, criminal, bankruptcy
- Justia Dockets — federal courts public search
- UniCourt API — state + federal court records aggregator
- RECAP Archive — crowdsourced PACER documents
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

_COURTLISTENER_API = "https://www.courtlistener.com/api/rest/v3"
_COURTLISTENER_SEARCH = "https://www.courtlistener.com/api/rest/v3/search/"
_JUSTIA_SEARCH = "https://law.justia.com/search/?q={query}"
_RECAP_SEARCH = "https://www.courtlistener.com/api/rest/v3/dockets/?q={query}"

# Case type indicators
_CRIMINAL_PATTERNS = re.compile(
    r'(?i)(criminal|felony|misdemeanor|indictment|arrest|conviction|'
    r'plea|sentencing|probation|parole|defendant)',
)
_CIVIL_PATTERNS = re.compile(
    r'(?i)(civil|plaintiff|defendant|complaint|lawsuit|settlement|'
    r'injunction|damages|breach of contract)',
)
_BANKRUPTCY_PATTERNS = re.compile(
    r'(?i)(bankruptcy|chapter 7|chapter 11|chapter 13|debtor|creditor|'
    r'discharge|trustee|reorganization)',
)


class CourtRecordsScanner(BaseOsintScanner):
    """Public court records and legal filings OSINT scanner."""

    scanner_name = "court_records"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL,
                                        ScanInputType.USERNAME})
    cache_ttl = 86400
    scan_timeout = 45

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        cases: list[dict[str, Any]] = []

        # Clean query for court search
        search_query = query.replace("@", " ").replace(".", " ").strip()
        if input_type == ScanInputType.DOMAIN:
            # Extract company/org name from domain
            search_query = query.split(".")[0].replace("-", " ").replace("_", " ")

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; CourtRecordsScanner/1.0)",
                "Accept": "application/json",
            },
        ) as client:
            semaphore = asyncio.Semaphore(3)

            # 1. CourtListener search
            async def search_courtlistener() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_COURTLISTENER_SEARCH}",
                            params={
                                "q": search_query,
                                "type": "r",  # RECAP
                                "order_by": "score desc",
                                "format": "json",
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            results = data.get("results", [])
                            total = data.get("count", 0)

                            if total > 0:
                                identifiers.append("info:courts:courtlistener_found")
                                for r in results[:5]:
                                    case_name = r.get("caseName", "Unknown")
                                    court = r.get("court", "")
                                    date_filed = r.get("dateFiled", "")
                                    docket_number = r.get("docketNumber", "")
                                    description_text = r.get("snippet", "")

                                    case_type = "civil"
                                    if _CRIMINAL_PATTERNS.search(description_text + case_name):
                                        case_type = "criminal"
                                    elif _BANKRUPTCY_PATTERNS.search(description_text + case_name):
                                        case_type = "bankruptcy"

                                    case_data = {
                                        "case_name": case_name,
                                        "docket_number": docket_number,
                                        "court": court,
                                        "date_filed": date_filed,
                                        "case_type": case_type,
                                        "source": "CourtListener",
                                        "url": f"https://www.courtlistener.com{r.get('absolute_url', '')}",
                                    }
                                    cases.append(case_data)

                                severity = "high" if any(
                                    c["case_type"] == "criminal" for c in cases
                                ) else "medium"

                                findings.append({
                                    "type": "court_records_found",
                                    "severity": severity,
                                    "source": "CourtListener / PACER",
                                    "query": search_query,
                                    "total_cases": total,
                                    "criminal_cases": sum(1 for c in cases if c["case_type"] == "criminal"),
                                    "civil_cases": sum(1 for c in cases if c["case_type"] == "civil"),
                                    "sample_cases": cases[:5],
                                    "description": f"Court records: {total} cases found for '{search_query}' — "
                                                   f"{sum(1 for c in cases if c['case_type'] == 'criminal')} criminal",
                                })
                    except Exception as exc:
                        log.debug("CourtListener error", error=str(exc))

            # 2. CourtListener opinion search (published opinions)
            async def search_opinions() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_COURTLISTENER_SEARCH}",
                            params={
                                "q": f'"{search_query}"',
                                "type": "o",  # opinions
                                "format": "json",
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            total = data.get("count", 0)
                            if total > 0:
                                results = data.get("results", [])
                                identifiers.append("info:courts:opinions_found")
                                findings.append({
                                    "type": "court_opinions_found",
                                    "severity": "info",
                                    "source": "CourtListener Opinions",
                                    "query": search_query,
                                    "total_opinions": total,
                                    "sample_opinions": [
                                        {
                                            "case_name": r.get("caseName"),
                                            "court": r.get("court"),
                                            "date_filed": r.get("dateFiled"),
                                        }
                                        for r in results[:3]
                                    ],
                                    "description": f"{total} published court opinions mention '{search_query}'",
                                })
                    except Exception as exc:
                        log.debug("CourtListener opinions error", error=str(exc))

            # 3. Justia search (broader US law search)
            async def search_justia() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            _JUSTIA_SEARCH.format(query=quote(f'"{search_query}"')),
                            headers={"Accept": "text/html"},
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            result_count = re.search(r'(\d[\d,]*)\s+result', body, re.I)
                            if result_count:
                                count_str = result_count.group(1).replace(",", "")
                                count = int(count_str)
                                if count > 0:
                                    identifiers.append("info:courts:justia_found")
                                    findings.append({
                                        "type": "justia_records_found",
                                        "severity": "info",
                                        "source": "Justia",
                                        "query": search_query,
                                        "result_count": count,
                                        "url": _JUSTIA_SEARCH.format(query=quote(f'"{search_query}"')),
                                        "description": f"Justia: {count} legal records for '{search_query}'",
                                    })
                    except Exception as exc:
                        log.debug("Justia error", error=str(exc))

            await asyncio.gather(search_courtlistener(), search_opinions(), search_justia())

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "search_query": search_query,
            "cases": cases,
            "findings": findings,
            "total_found": len(findings),
            "total_cases": len(cases),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
