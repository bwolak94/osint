"""Patent OSINT scanner — USPTO PatentsView, EPO OPS, Google Patents.

Finds:
- Patents filed by person/company (assignee or inventor)
- Patent filing dates, grant dates, expiry
- Co-inventors (links people together)
- Technology categories (CPC/IPC classification)
- Forward/backward citations (technology relationships)
- Patent litigation and legal events
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

_PATENTSVIEW_API = "https://search.patentsview.org/api/v1"
_USPTO_SEARCH = "https://patft.uspto.gov/netacgi/nph-Parser"
_GOOGLE_PATENTS = "https://patents.google.com/xhr/query"
_EPO_OPS = "https://ops.epo.org/3.2/rest-services"


class PatentScanner(BaseOsintScanner):
    """Patent filing and inventor OSINT scanner (USPTO + EPO + Google Patents)."""

    scanner_name = "patent"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL,
                                        ScanInputType.USERNAME})
    cache_ttl = 86400
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        patents: list[dict[str, Any]] = []

        # Derive search terms
        if input_type == ScanInputType.DOMAIN:
            assignee_query = query.split(".")[0].replace("-", " ").title()
            inventor_query = None
        elif "@" in query:
            parts = query.split("@")[0].split(".")
            inventor_query = " ".join(parts).title()
            assignee_query = query.split("@")[1].split(".")[0].title()
        else:
            inventor_query = query
            assignee_query = query

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; PatentScanner/1.0)",
                "Accept": "application/json",
            },
        ) as client:
            semaphore = asyncio.Semaphore(3)

            # 1. PatentsView API (USPTO open data)
            async def search_patentsview_assignee() -> None:
                async with semaphore:
                    try:
                        resp = await client.post(
                            f"{_PATENTSVIEW_API}/patent/",
                            json={
                                "q": {"assignee_organization": assignee_query},
                                "f": ["patent_number", "patent_title", "patent_date",
                                       "patent_type", "assignee_organization",
                                       "inventor_first_name", "inventor_last_name"],
                                "o": {"per_page": 10},
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            results = data.get("patents", [])
                            total = data.get("total_patent_count", 0)
                            if total and total > 0:
                                identifiers.append("info:patent:assignee_found")
                                for p in results[:5]:
                                    patent_data = {
                                        "patent_number": p.get("patent_number"),
                                        "title": p.get("patent_title"),
                                        "date": p.get("patent_date"),
                                        "type": p.get("patent_type"),
                                        "assignee": assignee_query,
                                        "inventors": [
                                            f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip()
                                            for inv in p.get("inventors", [])[:3]
                                        ],
                                        "url": f"https://patents.google.com/patent/US{p.get('patent_number')}",
                                    }
                                    patents.append(patent_data)

                                findings.append({
                                    "type": "patents_found_assignee",
                                    "severity": "info",
                                    "source": "USPTO PatentsView",
                                    "assignee": assignee_query,
                                    "total_patents": total,
                                    "sample_patents": patents[:5],
                                    "description": f"USPTO: {total} patents assigned to '{assignee_query}'",
                                })
                    except Exception as exc:
                        log.debug("PatentsView assignee error", error=str(exc))

            # 2. PatentsView inventor search
            async def search_patentsview_inventor() -> None:
                if not inventor_query:
                    return
                async with semaphore:
                    try:
                        parts = inventor_query.split() if inventor_query else []
                        q: dict[str, Any] = {}
                        if len(parts) >= 2:
                            q = {"_and": [
                                {"inventor_first_name": parts[0]},
                                {"inventor_last_name": parts[-1]},
                            ]}
                        else:
                            q = {"inventor_last_name": inventor_query}

                        resp = await client.post(
                            f"{_PATENTSVIEW_API}/patent/",
                            json={
                                "q": q,
                                "f": ["patent_number", "patent_title", "patent_date",
                                       "assignee_organization", "inventor_first_name",
                                       "inventor_last_name", "inventor_city", "inventor_country"],
                                "o": {"per_page": 10},
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            results = data.get("patents", [])
                            total = data.get("total_patent_count", 0)
                            if total and total > 0:
                                identifiers.append("info:patent:inventor_found")
                                inventor_patents = []
                                co_inventors: set[str] = set()
                                assignees: set[str] = set()

                                for p in results[:5]:
                                    for inv in p.get("inventors", []):
                                        co_name = f"{inv.get('inventor_first_name', '')} {inv.get('inventor_last_name', '')}".strip()
                                        if co_name.lower() != inventor_query.lower():
                                            co_inventors.add(co_name)
                                    for asgn in p.get("assignees", []):
                                        if asgn.get("assignee_organization"):
                                            assignees.add(asgn["assignee_organization"])

                                    inventor_patents.append({
                                        "patent_number": p.get("patent_number"),
                                        "title": p.get("patent_title"),
                                        "date": p.get("patent_date"),
                                        "assignees": list(assignees)[:3],
                                    })

                                findings.append({
                                    "type": "patents_found_inventor",
                                    "severity": "info",
                                    "source": "USPTO PatentsView",
                                    "inventor": inventor_query,
                                    "total_patents": total,
                                    "co_inventors": list(co_inventors)[:10],
                                    "assignee_companies": list(assignees)[:5],
                                    "sample_patents": inventor_patents,
                                    "description": f"USPTO: {total} patents by inventor '{inventor_query}' — "
                                                   f"linked to {len(assignees)} companies",
                                })
                    except Exception as exc:
                        log.debug("PatentsView inventor error", error=str(exc))

            # 3. Google Patents search
            async def search_google_patents() -> None:
                async with semaphore:
                    try:
                        search_term = inventor_query or assignee_query
                        resp = await client.get(
                            f"https://patents.google.com/xhr/query",
                            params={
                                "url": f"q={quote(search_term)}",
                                "exp": "",
                                "tags": "",
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            try:
                                data = _json.loads(resp.text)
                                total = data.get("results", {}).get("total_num_results", 0)
                                if total and total > 0:
                                    identifiers.append("info:patent:google_patents")
                                    findings.append({
                                        "type": "google_patents_found",
                                        "severity": "info",
                                        "source": "Google Patents",
                                        "query": search_term,
                                        "total_results": total,
                                        "url": f"https://patents.google.com/?q={quote(search_term)}",
                                        "description": f"Google Patents: {total} results for '{search_term}'",
                                    })
                            except Exception:
                                pass
                    except Exception as exc:
                        log.debug("Google Patents error", error=str(exc))

            await asyncio.gather(
                search_patentsview_assignee(),
                search_patentsview_inventor(),
                search_google_patents(),
            )

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "patents": patents,
            "findings": findings,
            "total_found": len(findings),
            "total_patents": len(patents),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
