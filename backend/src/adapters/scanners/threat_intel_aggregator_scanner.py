"""Threat Intel Aggregator — consolidates IoC data from multiple free threat intel sources.

Module 127 in the Infrastructure & Exploitation domain. Queries AlienVault OTX,
AbuseIPDB, and ThreatFox simultaneously for the target IP or domain and aggregates
the results into a unified threat intelligence report with IoC classification,
pulse counts, abuse confidence scores, and malware family associations.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OTX_BASE = "https://otx.alienvault.com/api/v1"
_ABUSEIPDB_BASE = "https://api.abuseipdb.com/api/v2"
_THREATFOX_BASE = "https://threatfox-api.abuse.ch/api/v1"


async def _query_otx(
    client: httpx.AsyncClient,
    target: str,
    input_type: ScanInputType,
    api_key: str,
) -> dict[str, Any]:
    """Query AlienVault OTX for threat pulses on the target."""
    endpoint_type = "IPv4" if input_type == ScanInputType.IP_ADDRESS else "domain"
    url = f"{_OTX_BASE}/indicators/{endpoint_type}/{target}/general"
    headers = {"X-OTX-API-KEY": api_key} if api_key else {}
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            pulses = data.get("pulse_info", {})
            return {
                "source": "AlienVault OTX",
                "found": pulses.get("count", 0) > 0,
                "pulse_count": pulses.get("count", 0),
                "tags": list({tag for p in pulses.get("pulses", []) for tag in p.get("tags", [])})[:20],
                "malware_families": list({
                    mf.get("display_name", "")
                    for p in pulses.get("pulses", [])
                    for mf in p.get("malware_families", [])
                    if mf.get("display_name")
                })[:10],
                "adversary": data.get("adversary", ""),
                "reputation": data.get("reputation", 0),
            }
        return {"source": "AlienVault OTX", "found": False, "error": f"HTTP {resp.status_code}"}
    except httpx.RequestError as exc:
        return {"source": "AlienVault OTX", "found": False, "error": str(exc)}


async def _query_abuseipdb(
    client: httpx.AsyncClient,
    target: str,
    input_type: ScanInputType,
    api_key: str,
) -> dict[str, Any]:
    """Query AbuseIPDB for abuse confidence score (IP only)."""
    if input_type != ScanInputType.IP_ADDRESS:
        return {"source": "AbuseIPDB", "found": False, "note": "AbuseIPDB only supports IP addresses"}
    if not api_key:
        return {"source": "AbuseIPDB", "found": False, "note": "ABUSEIPDB_API_KEY not configured"}

    try:
        resp = await client.get(
            f"{_ABUSEIPDB_BASE}/check",
            params={"ipAddress": target, "maxAgeInDays": 90, "verbose": ""},
            headers={"Key": api_key, "Accept": "application/json"},
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return {
                "source": "AbuseIPDB",
                "found": data.get("abuseConfidenceScore", 0) > 0,
                "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                "total_reports": data.get("totalReports", 0),
                "last_reported_at": data.get("lastReportedAt", ""),
                "country_code": data.get("countryCode", ""),
                "isp": data.get("isp", ""),
                "usage_type": data.get("usageType", ""),
                "is_whitelisted": data.get("isWhitelisted", False),
            }
        return {"source": "AbuseIPDB", "found": False, "error": f"HTTP {resp.status_code}"}
    except httpx.RequestError as exc:
        return {"source": "AbuseIPDB", "found": False, "error": str(exc)}


async def _query_threatfox(
    client: httpx.AsyncClient,
    target: str,
    input_type: ScanInputType,
) -> dict[str, Any]:
    """Query ThreatFox for IoC data."""
    ioc_type = "ip:port" if input_type == ScanInputType.IP_ADDRESS else "domain"
    try:
        resp = await client.post(
            _THREATFOX_BASE,
            json={"query": "search_ioc", "search_term": target},
            headers={"API-KEY": ""},  # ThreatFox allows anonymous queries
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("query_status") == "ok":
                iocs = data.get("data", [])
                return {
                    "source": "ThreatFox",
                    "found": len(iocs) > 0,
                    "ioc_count": len(iocs),
                    "iocs": [
                        {
                            "ioc": ioc.get("ioc", ""),
                            "ioc_type": ioc.get("ioc_type", ""),
                            "malware": ioc.get("malware", ""),
                            "confidence_level": ioc.get("confidence_level", 0),
                            "first_seen": ioc.get("first_seen", ""),
                            "last_seen": ioc.get("last_seen", ""),
                            "tags": ioc.get("tags", []),
                        }
                        for ioc in iocs[:10]
                    ],
                }
            return {"source": "ThreatFox", "found": False, "query_status": data.get("query_status")}
        return {"source": "ThreatFox", "found": False, "error": f"HTTP {resp.status_code}"}
    except httpx.RequestError as exc:
        return {"source": "ThreatFox", "found": False, "error": str(exc)}


class ThreatIntelAggregatorScanner(BaseOsintScanner):
    """Aggregates IoC data from AlienVault OTX, AbuseIPDB, and ThreatFox.

    Queries all three sources concurrently and produces a consolidated threat
    intelligence report with pulse counts, abuse scores, malware family associations,
    and IoC classifications. Uses free API tiers and public anonymous access
    where available (Module 127).
    """

    scanner_name = "threat_intel_aggregator"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN})
    cache_ttl = 14400  # 4 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = input_value.strip()
        otx_key = os.getenv("OTX_API_KEY", "")
        abuseipdb_key = os.getenv("ABUSEIPDB_API_KEY", "")

        async with httpx.AsyncClient(timeout=25) as client:
            otx_result, abuseipdb_result, threatfox_result = await asyncio.gather(
                _query_otx(client, target, input_type, otx_key),
                _query_abuseipdb(client, target, input_type, abuseipdb_key),
                _query_threatfox(client, target, input_type),
                return_exceptions=True,
            )

        sources: list[dict[str, Any]] = []
        for result in [otx_result, abuseipdb_result, threatfox_result]:
            if isinstance(result, dict):
                sources.append(result)
            else:
                sources.append({"found": False, "error": str(result)})

        any_found = any(s.get("found", False) for s in sources)

        # Determine severity from AbuseIPDB score if available
        abuse_score = 0
        for s in sources:
            if s.get("source") == "AbuseIPDB":
                abuse_score = s.get("abuse_confidence_score", 0)

        severity = "None"
        if any_found:
            if abuse_score >= 75:
                severity = "Critical"
            elif abuse_score >= 25:
                severity = "High"
            else:
                severity = "Medium"

        return {
            "target": target,
            "input_type": input_type.value,
            "found": any_found,
            "severity": severity,
            "sources": sources,
            "summary": {
                "threat_intelligence_sources_queried": len(sources),
                "sources_with_findings": sum(1 for s in sources if s.get("found")),
                "abuse_confidence_score": abuse_score,
                "otx_pulse_count": next((s.get("pulse_count", 0) for s in sources if s.get("source") == "AlienVault OTX"), 0),
                "threatfox_ioc_count": next((s.get("ioc_count", 0) for s in sources if s.get("source") == "ThreatFox"), 0),
            },
        }
