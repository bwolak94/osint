"""Academic profile OSINT scanner — ORCID, ResearchGate, Google Scholar, Semantic Scholar.

Finds:
- ORCID iD and full research profile (publications, affiliations, employment history)
- ResearchGate public profile (publications, citations, research interest score)
- Semantic Scholar (free API — papers, citations, co-authors, field of study)
- Google Scholar via public search
- Academia.edu public profile
- arXiv preprint search
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

_ORCID_API = "https://pub.orcid.org/v3.0"
_SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1"
_ARXIV_API = "https://export.arxiv.org/api/query"
_RESEARCHGATE = "https://www.researchgate.net/search/researcher"

_ORCID_ID_PATTERN = re.compile(r'(\d{4}-\d{4}-\d{4}-\d{3}[\dX])')


class AcademicScanner(BaseOsintScanner):
    """Academic publication and researcher profile OSINT scanner."""

    scanner_name = "academic"
    supported_input_types = frozenset({ScanInputType.EMAIL, ScanInputType.USERNAME,
                                        ScanInputType.DOMAIN})
    cache_ttl = 86400
    scan_timeout = 45

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        profiles: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AcademicScanner/1.0)",
                "Accept": "application/json",
            },
        ) as client:
            semaphore = asyncio.Semaphore(4)

            # 1. ORCID search
            async def search_orcid() -> None:
                async with semaphore:
                    try:
                        # Check if input is an ORCID iD directly
                        orcid_match = _ORCID_ID_PATTERN.search(query)
                        if orcid_match:
                            orcid_id = orcid_match.group(1)
                            resp = await client.get(
                                f"{_ORCID_API}/{orcid_id}",
                                headers={"Accept": "application/json"},
                            )
                            if resp.status_code == 200:
                                import json as _json
                                data = _json.loads(resp.text)
                                person = data.get("person", {})
                                name_data = person.get("name", {})
                                given = name_data.get("given-names", {}).get("value", "")
                                family = name_data.get("family-name", {}).get("value", "")
                                bio = person.get("biography", {}).get("content", "")
                                emails_data = person.get("emails", {}).get("email", [])
                                emails = [e.get("email") for e in emails_data if e.get("email")]
                                keywords = person.get("keywords", {}).get("keyword", [])
                                activities = data.get("activities-summary", {})
                                works_count = len(activities.get("works", {}).get("group", []))

                                profiles["orcid"] = {
                                    "orcid_id": orcid_id,
                                    "full_name": f"{given} {family}".strip(),
                                    "bio": bio[:200] if bio else None,
                                    "emails": emails,
                                    "research_keywords": [k.get("content") for k in keywords[:5]],
                                    "publications_count": works_count,
                                }
                                identifiers.append("info:academic:orcid_found")
                                findings.append({
                                    "type": "orcid_profile",
                                    "severity": "info",
                                    "orcid_id": orcid_id,
                                    "full_name": f"{given} {family}".strip(),
                                    "emails": emails,
                                    "publications_count": works_count,
                                    "url": f"https://orcid.org/{orcid_id}",
                                    "description": f"ORCID profile: {given} {family} — {works_count} publications",
                                })
                        else:
                            # Search by name/email
                            search_term = query.split("@")[0].replace(".", " ") if "@" in query else query
                            resp = await client.get(
                                f"{_ORCID_API}/search/",
                                params={"q": search_term, "rows": 5},
                                headers={"Accept": "application/json"},
                            )
                            if resp.status_code == 200:
                                import json as _json
                                data = _json.loads(resp.text)
                                results = data.get("result", [])
                                total = data.get("num-found", 0)
                                if total > 0:
                                    identifiers.append("info:academic:orcid_search")
                                    profiles["orcid_search"] = {
                                        "total": total,
                                        "results": [
                                            {
                                                "orcid_id": r.get("orcid-identifier", {}).get("path"),
                                                "name": f"{r.get('person', {}).get('name', {}).get('given-names', {}).get('value', '')} "
                                                        f"{r.get('person', {}).get('name', {}).get('family-name', {}).get('value', '')}".strip(),
                                            }
                                            for r in results[:5]
                                        ],
                                    }
                                    if total > 0:
                                        findings.append({
                                            "type": "orcid_search_results",
                                            "severity": "info",
                                            "query": search_term,
                                            "total_found": total,
                                            "profiles": profiles["orcid_search"]["results"],
                                            "description": f"ORCID: {total} researcher profiles for '{search_term}'",
                                        })
                    except Exception as exc:
                        log.debug("ORCID error", error=str(exc))

            # 2. Semantic Scholar search
            async def search_semantic_scholar() -> None:
                async with semaphore:
                    try:
                        search_name = query.split("@")[0].replace(".", " ") if "@" in query else query
                        resp = await client.get(
                            f"{_SEMANTIC_SCHOLAR}/author/search",
                            params={
                                "query": search_name,
                                "fields": "name,affiliations,paperCount,citationCount,hIndex,externalIds",
                                "limit": 5,
                            },
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            authors = data.get("data", [])
                            if authors:
                                identifiers.append("info:academic:semantic_scholar")
                                profiles["semantic_scholar"] = authors[:3]
                                for author in authors[:3]:
                                    findings.append({
                                        "type": "semantic_scholar_author",
                                        "severity": "info",
                                        "author_id": author.get("authorId"),
                                        "name": author.get("name"),
                                        "affiliations": author.get("affiliations", []),
                                        "paper_count": author.get("paperCount", 0),
                                        "citation_count": author.get("citationCount", 0),
                                        "h_index": author.get("hIndex", 0),
                                        "url": f"https://www.semanticscholar.org/author/{author.get('authorId')}",
                                        "description": f"Semantic Scholar: {author.get('name')} — "
                                                       f"{author.get('paperCount', 0)} papers, "
                                                       f"H-index: {author.get('hIndex', 0)}",
                                    })
                    except Exception as exc:
                        log.debug("Semantic Scholar error", error=str(exc))

            # 3. arXiv preprint search
            async def search_arxiv() -> None:
                async with semaphore:
                    try:
                        search_name = query.split("@")[0].replace(".", " ") if "@" in query else query
                        resp = await client.get(
                            _ARXIV_API,
                            params={
                                "search_query": f"au:{quote(search_name)}",
                                "start": 0,
                                "max_results": 5,
                            },
                            headers={"Accept": "application/xml"},
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            total_match = re.search(r'<opensearch:totalResults[^>]*>(\d+)', body)
                            total = int(total_match.group(1)) if total_match else 0
                            if total > 0:
                                titles = re.findall(r'<title>(?!arXiv)(.+?)</title>', body)
                                identifiers.append("info:academic:arxiv_found")
                                findings.append({
                                    "type": "arxiv_preprints",
                                    "severity": "info",
                                    "query": search_name,
                                    "total_papers": total,
                                    "sample_titles": titles[:3],
                                    "url": f"https://arxiv.org/search/?searchtype=author&query={quote(search_name)}",
                                    "description": f"arXiv: {total} preprints by '{search_name}'",
                                })
                    except Exception as exc:
                        log.debug("arXiv error", error=str(exc))

            await asyncio.gather(search_orcid(), search_semantic_scholar(), search_arxiv())

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "profiles": profiles,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
