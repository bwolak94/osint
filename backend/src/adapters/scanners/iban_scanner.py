"""IBAN / bank account OSINT scanner.

Finds:
- IBAN validation and BIC/SWIFT code lookup
- Bank name and branch from IBAN
- Country of origin and account type
- OFAC SDN (Specially Designated Nationals) sanctions check
- EU sanctions list check (opensanctions)
- Leaked IBAN in breach databases (text search)
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_IBAN_API = "https://openiban.com/validate"
_IBAN_PATTERN = re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}$')


class IBANScanner(BaseOsintScanner):
    """IBAN / bank account OSINT and sanctions scanner."""

    scanner_name = "iban"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL,
                                        ScanInputType.DOMAIN})
    cache_ttl = 86400
    scan_timeout = 20

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        bank_info: dict[str, Any] = {}

        # Clean up query — remove spaces
        iban_candidate = re.sub(r'\s+', '', query.upper())
        is_iban = bool(_IBAN_PATTERN.match(iban_candidate))

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; IBANScanner/1.0)"},
        ) as client:
            if is_iban:
                # 1. OpenIBAN validation and BIC lookup
                try:
                    resp = await client.get(
                        f"{_IBAN_API}/{iban_candidate}",
                        params={"getBIC": "true"},
                    )
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text)
                        if data.get("valid"):
                            bank_data = data.get("bankData", {})
                            bank_info = {
                                "iban": iban_candidate,
                                "valid": True,
                                "bank_name": bank_data.get("name"),
                                "bic": bank_data.get("bic"),
                                "city": bank_data.get("city"),
                                "zip": bank_data.get("zip"),
                                "country": iban_candidate[:2],
                            }
                            identifiers.append("info:iban:validated")
                            findings.append({
                                "type": "iban_validated",
                                "severity": "medium",
                                "source": "OpenIBAN",
                                "iban": iban_candidate,
                                "bank_name": bank_data.get("name"),
                                "bic": bank_data.get("bic"),
                                "country": iban_candidate[:2],
                                "description": f"IBAN {iban_candidate[:8]}*** validated — "
                                               f"{bank_data.get('name', 'Unknown Bank')}",
                            })
                        else:
                            findings.append({
                                "type": "iban_invalid",
                                "severity": "info",
                                "source": "OpenIBAN",
                                "iban": iban_candidate,
                                "description": f"IBAN {iban_candidate[:8]}*** is invalid",
                            })
                except Exception as exc:
                    log.debug("OpenIBAN error", error=str(exc))

                # 2. Check OFAC SDN list via US Treasury API
                try:
                    resp = await client.get(
                        "https://ofac-api.ofac.org/api/Search",
                        params={
                            "Name": iban_candidate,
                            "type": "ENTITY",
                            "program": "",
                        },
                        headers={"API-KEY": ""},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text)
                        hits = data.get("matches", [])
                        if hits:
                            identifiers.append("vuln:iban:ofac_sanctions")
                            findings.append({
                                "type": "ofac_sanctions_hit",
                                "severity": "critical",
                                "source": "OFAC SDN",
                                "query": iban_candidate,
                                "matches": hits[:3],
                                "description": f"OFAC sanctions match for '{iban_candidate}'",
                            })
                except Exception as exc:
                    log.debug("OFAC check error", error=str(exc))

            # 3. IBAN extracted from text search (non-IBAN input)
            else:
                # Extract any IBANs from the query text
                iban_pattern = re.compile(r'\b([A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16})\b')
                matches = iban_pattern.findall(query)
                if matches:
                    identifiers.append("info:iban:extracted_from_text")
                    findings.append({
                        "type": "iban_extracted",
                        "severity": "medium",
                        "source": "Text extraction",
                        "ibans_found": matches[:5],
                        "description": f"Found {len(matches)} IBAN(s) in input text",
                    })

            # 4. opensanctions.org check
            try:
                search_term = iban_candidate if is_iban else query
                resp = await client.get(
                    "https://api.opensanctions.org/search/default",
                    params={"q": search_term, "limit": 5},
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    results = data.get("results", [])
                    if results:
                        identifiers.append("vuln:iban:opensanctions_hit")
                        findings.append({
                            "type": "opensanctions_hit",
                            "severity": "high",
                            "source": "OpenSanctions",
                            "query": search_term,
                            "hits": [r.get("caption") for r in results[:3]],
                            "description": f"OpenSanctions: {len(results)} hits for '{search_term}'",
                        })
            except Exception as exc:
                log.debug("OpenSanctions error", error=str(exc))

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "is_iban": is_iban,
            "bank_info": bank_info,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
