"""ASN/BGP route scanner — autonomous system and routing information."""

import asyncio
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class ASNScanner(BaseOsintScanner):
    scanner_name = "asn"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Use bgpview.io free API
        async with httpx.AsyncClient(timeout=15) as client:
            if input_type == ScanInputType.IP_ADDRESS:
                return await self._lookup_ip(client, input_value)
            return await self._lookup_domain(client, input_value)

    async def _lookup_ip(self, client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
        resp = await client.get(f"https://api.bgpview.io/ip/{ip}")

        if resp.status_code != 200:
            return {"input": ip, "found": False, "extracted_identifiers": []}

        data = resp.json().get("data", {})
        prefixes = data.get("prefixes", [])

        identifiers: list[str] = []
        asn_info: dict[str, Any] = {}
        if prefixes:
            first = prefixes[0]
            asn = first.get("asn", {})
            asn_info = {
                "asn": asn.get("asn"),
                "asn_name": asn.get("name", ""),
                "asn_description": asn.get("description", ""),
                "asn_country": asn.get("country_code", ""),
                "prefix": first.get("prefix", ""),
                "ip": first.get("ip", ip),
            }
            if asn.get("asn"):
                identifiers.append(f"asn:{asn['asn']}")
            if first.get("prefix"):
                identifiers.append(f"prefix:{first['prefix']}")

        return {
            "input": ip,
            "found": bool(prefixes),
            **asn_info,
            "prefix_count": len(prefixes),
            "all_prefixes": [p.get("prefix") for p in prefixes],
            "extracted_identifiers": identifiers,
        }

    async def _lookup_domain(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        # First resolve domain to IP, then lookup ASN
        try:
            loop = asyncio.get_running_loop()
            result = await loop.getaddrinfo(domain, None, family=socket.AF_INET)
            if not result:
                return {"input": domain, "found": False, "extracted_identifiers": []}
            ip = result[0][4][0]
            data = await self._lookup_ip(client, ip)
            data["input"] = domain
            data["resolved_ip"] = ip
            return data
        except Exception as e:
            log.warning("Domain resolution failed for ASN lookup", domain=domain, error=str(e))
            return {"input": domain, "found": False, "error": str(e), "extracted_identifiers": []}
