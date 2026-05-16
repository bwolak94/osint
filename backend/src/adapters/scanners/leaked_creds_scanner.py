"""Leaked credentials aggregator — Dehashed, BreachDirectory, LeakCheck, IntelligenceX.

Goes beyond HIBP to find:
- Plaintext or hashed passwords in breach databases
- Associated IP addresses from credential stuffing lists
- Username/email/phone combinations across multiple leaked datasets
- Source breach names, dates, and context
- BreachDirectory (free): email → password hashes + breach names
- LeakCheck API: email → credential pairs
- IntelligenceX: deep leak search across darknet + Pastebin + forums
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BREACHDIR_API = "https://breachdirectory.p.rapidapi.com/"
_LEAKCHECK_API = "https://leakcheck.io/api/public"
_INTELX_API = "https://2.intelx.io"
_SNUSBASE_API = "https://api-experimental.snusbase.com"
_DEHASHED_API = "https://api.dehashed.com/search"
_PROXYNOVA_API = "https://api.proxynova.com/comb"


class LeakedCredsScanner(BaseOsintScanner):
    """Multi-source leaked credentials scanner.

    Queries BreachDirectory, LeakCheck, Proxynova COMB, and IntelligenceX
    for credential pairs, breach sources, and associated data.
    """

    scanner_name = "leaked_creds"
    supported_input_types = frozenset({ScanInputType.EMAIL, ScanInputType.DOMAIN,
                                        ScanInputType.USERNAME})
    cache_ttl = 3600
    scan_timeout = 45

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        breaches: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LeakScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(4)

            # 1. BreachDirectory (free public endpoint)
            async def query_breachdirectory() -> None:
                async with semaphore:
                    try:
                        sha1 = hashlib.sha1(query.lower().encode()).hexdigest().upper()
                        prefix = sha1[:5]
                        resp = await client.get(
                            f"https://breachdirectory.org/api?func=auto&term={query}",
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            if data.get("success") and data.get("result"):
                                results = data["result"]
                                for r in results[:10]:
                                    breaches.append({
                                        "source": "BreachDirectory",
                                        "email": r.get("email"),
                                        "password": r.get("password"),
                                        "hash": r.get("sha1"),
                                        "breach": r.get("sources", []),
                                    })
                                identifiers.append("vuln:leaks:breachdirectory")
                                findings.append({
                                    "type": "credentials_found",
                                    "severity": "critical",
                                    "source": "BreachDirectory",
                                    "query": query,
                                    "result_count": len(results),
                                    "sample": results[:3],
                                    "description": f"BreachDirectory: {len(results)} credential records found for {query}",
                                    "remediation": "Change passwords immediately; enable 2FA; check all services using same password",
                                })
                    except Exception as exc:
                        log.debug("BreachDirectory error", error=str(exc))

            # 2. LeakCheck.io public API (free, rate-limited)
            async def query_leakcheck() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_LEAKCHECK_API}?key=&type=auto&check={query}",
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            if data.get("success") and data.get("found", 0) > 0:
                                sources = data.get("sources", [])
                                identifiers.append("vuln:leaks:leakcheck")
                                findings.append({
                                    "type": "credentials_found",
                                    "severity": "critical",
                                    "source": "LeakCheck",
                                    "query": query,
                                    "found_count": data["found"],
                                    "breach_sources": [s.get("name") for s in sources[:10]],
                                    "description": f"LeakCheck: {data['found']} records in "
                                                   f"{len(sources)} breach sources",
                                    "remediation": "Change compromised passwords immediately",
                                })
                                for s in sources[:5]:
                                    breaches.append({
                                        "source": "LeakCheck",
                                        "breach_name": s.get("name"),
                                        "breach_date": s.get("date"),
                                    })
                    except Exception as exc:
                        log.debug("LeakCheck error", error=str(exc))

            # 3. Proxynova COMB (Collection of Many Breaches)
            async def query_proxynova() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_PROXYNOVA_API}?q={query}&start=0&limit=10",
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            lines = data.get("lines", [])
                            if lines:
                                identifiers.append("vuln:leaks:proxynova_comb")
                                # Parse credential pairs
                                cred_pairs = []
                                for line in lines[:10]:
                                    parts = str(line).split(":")
                                    if len(parts) >= 2:
                                        cred_pairs.append({
                                            "email": parts[0],
                                            "password": ":".join(parts[1:])[:50],
                                        })
                                if cred_pairs:
                                    findings.append({
                                        "type": "credentials_found_comb",
                                        "severity": "critical",
                                        "source": "Proxynova COMB",
                                        "query": query,
                                        "result_count": data.get("count", len(lines)),
                                        "sample_credentials": cred_pairs[:3],
                                        "description": f"COMB database: {data.get('count', len(lines))} "
                                                       f"credential pairs found for {query}",
                                        "remediation": "All listed passwords must be treated as compromised",
                                    })
                                    for pair in cred_pairs:
                                        breaches.append({
                                            "source": "COMB",
                                            "email": pair["email"],
                                            "password_hint": pair["password"][:3] + "***",
                                        })
                    except Exception as exc:
                        log.debug("Proxynova error", error=str(exc))

            # 4. Hudson Rock Cavalier (free cybercrime intelligence API)
            async def query_hudsonrock() -> None:
                async with semaphore:
                    try:
                        if "@" in query:
                            resp = await client.get(
                                f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/"
                                f"search-by-email?email={query}",
                            )
                        else:
                            resp = await client.get(
                                f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/"
                                f"search-by-domain?domain={query}",
                            )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            stealers = data.get("stealerFamilies", [])
                            total = data.get("total", 0)
                            if total > 0:
                                identifiers.append("vuln:leaks:stealer_log")
                                findings.append({
                                    "type": "stealer_log_found",
                                    "severity": "critical",
                                    "source": "Hudson Rock Cavalier",
                                    "query": query,
                                    "infected_count": total,
                                    "stealer_families": stealers[:5],
                                    "computers": data.get("data", [])[:3],
                                    "description": f"Infostealer malware logs: {total} infected computers "
                                                   f"with credentials for {query}",
                                    "remediation": "Affected accounts should be considered fully compromised; "
                                                   "rotate all credentials on infected machines",
                                })
                    except Exception as exc:
                        log.debug("HudsonRock error", error=str(exc))

            await asyncio.gather(
                query_breachdirectory(),
                query_leakcheck(),
                query_proxynova(),
                query_hudsonrock(),
            )

        severity_counts: dict[str, int] = {}
        for f in findings:
            s = f.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "query": query,
            "breaches": breaches[:20],
            "findings": findings,
            "total_found": len(findings),
            "total_credential_records": sum(
                f.get("result_count", f.get("found_count", 0)) for f in findings
            ),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
