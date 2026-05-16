"""SEC EDGAR insider trading & corporate intelligence scanner.

Uses SEC EDGAR full-text search and EDGAR REST API to find:
- Form 4 insider trading filings (buys/sells by officers/directors)
- 13D/13G large ownership disclosures
- 8-K material event filings
- Company CIK lookups and filing history
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_EDGAR_BASE = "https://efts.sec.gov"
_EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_EDGAR_API = "https://data.sec.gov"


class SECEdgarScanner(BaseOsintScanner):
    """SEC EDGAR corporate intelligence and insider trading scanner."""

    scanner_name = "sec_edgar"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL,
                                        ScanInputType.USERNAME})
    cache_ttl = 43200
    scan_timeout = 25

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        # Extract company name from domain/email
        company = query.split(".")[0].replace("-", " ") if "." in query else query
        if "@" in company:
            company = query.split("@")[1].split(".")[0]

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "OSINT-Scanner research@example.com",
                "Accept": "application/json",
            },
        ) as client:
            # 1. Search for company CIK via EDGAR full-text search
            try:
                resp = await client.get(
                    "https://efts.sec.gov/LATEST/search-index?q=%22{}&dateRange=custom&startdt=2020-01-01&forms=10-K".format(
                        quote(company)
                    ),
                    timeout=8,
                )
            except Exception:
                pass

            # 2. EDGAR company search API
            try:
                resp = await client.get(
                    f"https://efts.sec.gov/LATEST/search-index?q=%22{quote(company)}%22&forms=4",
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    hits = data.get("hits", {}).get("hits", [])
                    total = data.get("hits", {}).get("total", {}).get("value", 0)
                    if hits:
                        sample = [
                            {
                                "filed": h.get("_source", {}).get("file_date", ""),
                                "company": h.get("_source", {}).get("display_names", [""])[0] if h.get("_source", {}).get("display_names") else "",
                                "form": h.get("_source", {}).get("form_type", ""),
                                "description": h.get("_source", {}).get("period_of_report", ""),
                            }
                            for h in hits[:5]
                        ]
                        identifiers.append("medium:edgar:form4_found")
                        findings.append({
                            "type": "insider_trading_filings",
                            "severity": "medium",
                            "source": "SEC EDGAR Form 4",
                            "company": company,
                            "total_filings": total,
                            "sample_filings": sample,
                            "description": f"SEC Form 4: {total} insider transaction filings for '{company}'",
                        })
            except Exception as exc:
                log.debug("EDGAR Form 4 search error", error=str(exc))

            # 3. EDGAR full-text search for 8-K material events
            try:
                resp = await client.get(
                    f"https://efts.sec.gov/LATEST/search-index?q=%22{quote(company)}%22&forms=8-K&dateRange=custom&startdt=2023-01-01",
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    hits = data.get("hits", {}).get("hits", [])
                    total = data.get("hits", {}).get("total", {}).get("value", 0)
                    if hits:
                        identifiers.append("info:edgar:8k_found")
                        findings.append({
                            "type": "sec_material_events",
                            "severity": "low",
                            "source": "SEC EDGAR 8-K",
                            "company": company,
                            "total_events": total,
                            "recent_events": [
                                h.get("_source", {}).get("file_date", "") for h in hits[:3]
                            ],
                            "description": f"SEC 8-K: {total} material event disclosures for '{company}'",
                        })
            except Exception as exc:
                log.debug("EDGAR 8-K search error", error=str(exc))

            # 4. Large ownership disclosures (13D/13G)
            try:
                resp = await client.get(
                    f"https://efts.sec.gov/LATEST/search-index?q=%22{quote(company)}%22&forms=SC+13D,SC+13G",
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    total = data.get("hits", {}).get("total", {}).get("value", 0)
                    if total:
                        identifiers.append("info:edgar:ownership_disclosed")
                        findings.append({
                            "type": "large_ownership_disclosure",
                            "severity": "low",
                            "source": "SEC EDGAR 13D/13G",
                            "company": company,
                            "total_disclosures": total,
                            "description": f"SEC 13D/13G: {total} large ownership disclosures for '{company}'",
                        })
            except Exception as exc:
                log.debug("EDGAR 13D/13G search error", error=str(exc))

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "company": company,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
