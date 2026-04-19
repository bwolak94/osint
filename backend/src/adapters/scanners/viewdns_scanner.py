"""ViewDNS.info scanner — reverse WHOIS, IP history, and reverse DNS lookups."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://api.viewdns.info"


class ViewDNSScanner(BaseOsintScanner):
    """Queries ViewDNS.info API for reverse WHOIS, IP history, and reverse DNS.

    Requires viewdns_api_key in settings for JSON API access.
    - EMAIL: reversewhois — domains registered with this email/org
    - DOMAIN: iphistory — historical IP addresses for the domain
    - IP_ADDRESS: reversedns — hostnames pointing to this IP
    """

    scanner_name = "viewdns"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS, ScanInputType.EMAIL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()
        api_key: str = getattr(settings, "viewdns_api_key", "") or ""

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                if input_type == ScanInputType.EMAIL:
                    return await self._reverse_whois(client, input_value, api_key)
                if input_type == ScanInputType.DOMAIN:
                    return await self._ip_history(client, input_value, api_key)
                return await self._reverse_dns(client, input_value, api_key)
            except Exception as e:
                log.error("ViewDNS scan failed", input=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

    async def _reverse_whois(self, client: httpx.AsyncClient, email: str, api_key: str) -> dict[str, Any]:
        identifiers: list[str] = []
        domains: list[dict[str, Any]] = []

        if not api_key:
            log.warning("ViewDNS: no API key configured, reversewhois unavailable", email=email)
            return {
                "input": email,
                "found": False,
                "error": "viewdns_api_key not configured",
                "extracted_identifiers": [],
            }

        resp = await client.get(
            f"{_BASE_URL}/reversewhois/",
            params={"q": email, "apikey": api_key, "output": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

        response_data = data.get("response", {})
        for entry in response_data.get("domains", []):
            domain_name = entry.get("name", "")
            domains.append({
                "domain": domain_name,
                "registered_date": entry.get("registered_date", ""),
            })
            if domain_name:
                identifiers.append(f"domain:{domain_name}")

        return {
            "input": email,
            "found": bool(domains),
            "domains": domains,
            "domain_count": len(domains),
            "extracted_identifiers": identifiers,
        }

    async def _ip_history(self, client: httpx.AsyncClient, domain: str, api_key: str) -> dict[str, Any]:
        identifiers: list[str] = []
        history: list[dict[str, Any]] = []

        if not api_key:
            log.warning("ViewDNS: no API key configured, iphistory unavailable", domain=domain)
            return {
                "input": domain,
                "found": False,
                "error": "viewdns_api_key not configured",
                "extracted_identifiers": [],
            }

        resp = await client.get(
            f"{_BASE_URL}/iphistory/",
            params={"domain": domain, "apikey": api_key, "output": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

        response_data = data.get("response", {})
        for entry in response_data.get("records", []):
            ip = entry.get("ip", "")
            history.append({
                "ip": ip,
                "location": entry.get("location", ""),
                "owner": entry.get("owner", ""),
                "last_seen": entry.get("lastseen", ""),
            })
            if ip:
                identifiers.append(f"ip:{ip}")

        return {
            "input": domain,
            "found": bool(history),
            "ip_history": history,
            "extracted_identifiers": identifiers,
        }

    async def _reverse_dns(self, client: httpx.AsyncClient, ip: str, api_key: str) -> dict[str, Any]:
        identifiers: list[str] = []
        hostnames: list[str] = []

        if not api_key:
            log.warning("ViewDNS: no API key configured, reversedns unavailable", ip=ip)
            return {
                "input": ip,
                "found": False,
                "error": "viewdns_api_key not configured",
                "extracted_identifiers": [],
            }

        resp = await client.get(
            f"{_BASE_URL}/reversedns/",
            params={"ip": ip, "apikey": api_key, "output": "json"},
        )
        resp.raise_for_status()
        data = resp.json()

        response_data = data.get("response", {})
        rdns = response_data.get("rdns", "")
        if rdns:
            hostnames.append(rdns)
            identifiers.append(f"domain:{rdns}")

        return {
            "input": ip,
            "found": bool(hostnames),
            "hostnames": hostnames,
            "extracted_identifiers": identifiers,
        }
