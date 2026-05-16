"""WHOIS history / registrant pivot scanner.

Finds:
- Historical WHOIS records for a domain (registrant name, email, org)
- All domains registered by the same registrant email/name
- Domain ownership pivoting (who else did this person register?)
- Registrar history and transfer events
- Sources: SecurityTrails (unauthenticated), WhoisXML API, ViewDNS.info
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

_VIEWDNS_BASE = "https://viewdns.info"
_DOMAINTOOLS_BASE = "https://whois.domaintools.com"


class WhoisHistoryScanner(BaseOsintScanner):
    """Historical WHOIS registrant pivot scanner."""

    scanner_name = "whois_history"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL})
    cache_ttl = 86400
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        history: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/html",
            },
        ) as client:
            # 1. ViewDNS reverse WHOIS (email → domains)
            if "@" in query or input_type == ScanInputType.EMAIL:
                try:
                    resp = await client.get(
                        f"{_VIEWDNS_BASE}/reversewhois/",
                        params={"q": query},
                        headers={"Accept": "text/html"},
                    )
                    if resp.status_code == 200:
                        body = resp.text
                        # Extract domain count
                        count_match = re.search(r'(\d+)\s+domain', body, re.I)
                        domains = re.findall(r'<td>([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})</td>', body)
                        if count_match or domains:
                            total = int(count_match.group(1)) if count_match else len(domains)
                            identifiers.append("info:whois_history:reverse_whois")
                            findings.append({
                                "type": "reverse_whois_results",
                                "severity": "medium",
                                "source": "ViewDNS Reverse WHOIS",
                                "query": query,
                                "total_domains": total,
                                "sample_domains": list(set(domains))[:10],
                                "url": f"{_VIEWDNS_BASE}/reversewhois/?q={quote(query)}",
                                "description": f"Reverse WHOIS: {total} domains registered to '{query}'",
                            })
                except Exception as exc:
                    log.debug("ViewDNS reverse WHOIS error", error=str(exc))

            # 2. WHOIS history via SecurityTrails-compatible lookup
            if input_type == ScanInputType.DOMAIN:
                try:
                    resp = await client.get(
                        f"https://securitytrails.com/domain/{query}/history/whois",
                        headers={"Accept": "application/json"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        try:
                            data = _json.loads(resp.text)
                            records = data.get("result", {}).get("items", [])
                            if records:
                                identifiers.append("info:whois_history:history_found")
                                for r in records[:5]:
                                    history.append({
                                        "date": r.get("date"),
                                        "registrant_name": r.get("whois", {}).get("registrant", {}).get("name"),
                                        "registrant_email": r.get("whois", {}).get("registrant", {}).get("email"),
                                        "registrar": r.get("whois", {}).get("registrar", {}).get("name"),
                                    })
                                findings.append({
                                    "type": "whois_history_found",
                                    "severity": "info",
                                    "source": "SecurityTrails",
                                    "domain": query,
                                    "history_records": history,
                                    "description": f"WHOIS history: {len(records)} records for '{query}'",
                                })
                        except Exception:
                            pass
                except Exception as exc:
                    log.debug("SecurityTrails WHOIS history error", error=str(exc))

                # 3. WhoisXML API free tier
                try:
                    resp = await client.get(
                        "https://www.whoisxmlapi.com/whoisserver/WhoisService",
                        params={
                            "domainName": query,
                            "outputFormat": "JSON",
                            "apiKey": "at_free",
                        },
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        try:
                            data = _json.loads(resp.text)
                            record = data.get("WhoisRecord", {})
                            registrant = record.get("registrant", {})
                            if registrant:
                                identifiers.append("info:whois_history:current_whois")
                                findings.append({
                                    "type": "current_whois_registrant",
                                    "severity": "info",
                                    "source": "WhoisXML",
                                    "domain": query,
                                    "registrant_name": registrant.get("name"),
                                    "registrant_org": registrant.get("organization"),
                                    "registrant_email": registrant.get("email"),
                                    "registrant_country": registrant.get("country"),
                                    "created_date": record.get("createdDate"),
                                    "updated_date": record.get("updatedDate"),
                                    "expires_date": record.get("expiresDate"),
                                    "registrar": record.get("registrarName"),
                                    "description": f"Current WHOIS: {registrant.get('name') or registrant.get('organization', 'Unknown')} owns '{query}'",
                                })
                        except Exception:
                            pass
                except Exception as exc:
                    log.debug("WhoisXML error", error=str(exc))

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "history": history,
            "findings": findings,
            "total_found": len(findings),
            "total_history_records": len(history),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
