"""ThreatFox scanner — searches the abuse.ch ThreatFox IOC database."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_THREATFOX_API = "https://threatfox-api.abuse.ch/api/v1/"

# Rough pattern used to detect whether an arbitrary string looks like a hash
_HASH_RE = re.compile(r"^[0-9a-fA-F]{32,64}$")


class ThreatFoxScanner(BaseOsintScanner):
    """Queries the ThreatFox API (abuse.ch) for Indicators of Compromise.

    No API key required — the service is free.

    Supports IP_ADDRESS, DOMAIN, and URL input types.  Arbitrary hash values
    (MD5/SHA1/SHA256) embedded in a URL-typed input are also handled: if the
    value matches the hash regex the scanner performs an IOC search directly on
    that value.

    Returns matched IOC records, aggregated threat types, malware families, and
    an average confidence level.  Related domains and IPs found in the matched
    IOCs are surfaced as extracted identifiers.
    """

    scanner_name = "threatfox"
    supported_input_types = frozenset({
        ScanInputType.IP_ADDRESS,
        ScanInputType.DOMAIN,
        ScanInputType.URL,
    })
    cache_ttl = 1800

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        search_term = input_value
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._search_ioc(client, search_term)

    async def _search_ioc(self, client: httpx.AsyncClient, search_term: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": "search_ioc", "search_term": search_term}
        resp = await client.post(_THREATFOX_API, json=payload)
        resp.raise_for_status()
        data = resp.json()

        query_status = data.get("query_status", "")
        if query_status != "ok":
            return {
                "input": search_term,
                "found": False,
                "query_status": query_status,
                "total_matches": 0,
                "matches": [],
                "threat_types": [],
                "malware_families": [],
                "confidence_avg": 0.0,
                "extracted_identifiers": [],
            }

        iocs: list[dict[str, Any]] = data.get("data", []) or []

        threat_types: list[str] = []
        malware_families: list[str] = []
        confidence_sum = 0
        identifiers: list[str] = []
        matches: list[dict[str, Any]] = []

        for ioc in iocs:
            threat_type = ioc.get("threat_type", "")
            malware = ioc.get("malware_printable", "") or ioc.get("fk_malware", "")
            confidence = ioc.get("confidence_level", 0)

            if threat_type and threat_type not in threat_types:
                threat_types.append(threat_type)
            if malware and malware not in malware_families:
                malware_families.append(malware)
            confidence_sum += confidence

            # Collect related indicators from the IOC record
            ioc_value = ioc.get("ioc", "")
            ioc_type = ioc.get("ioc_type", "")
            if ioc_type == "domain" and ioc_value:
                ident = f"domain:{ioc_value}"
                if ident not in identifiers:
                    identifiers.append(ident)
            elif ioc_type in ("ip:port", "ip") and ioc_value:
                ip_part = ioc_value.split(":")[0]
                ident = f"ip:{ip_part}"
                if ident not in identifiers:
                    identifiers.append(ident)

            matches.append({
                "ioc_id": ioc.get("id"),
                "ioc_type": ioc_type,
                "ioc_value": ioc_value,
                "threat_type": threat_type,
                "malware": malware,
                "malware_alias": ioc.get("malware_alias"),
                "confidence_level": confidence,
                "first_seen": ioc.get("first_seen"),
                "last_seen": ioc.get("last_seen"),
                "reference": ioc.get("reference"),
                "tags": ioc.get("tags") or [],
                "reporter": ioc.get("reporter"),
            })

        total = len(matches)
        confidence_avg = round(confidence_sum / total, 2) if total else 0.0

        return {
            "input": search_term,
            "found": total > 0,
            "query_status": query_status,
            "total_matches": total,
            "matches": matches,
            "threat_types": threat_types,
            "malware_families": malware_families,
            "confidence_avg": confidence_avg,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
