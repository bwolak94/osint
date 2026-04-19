"""RIPEstat scanner — BGP routing, ASN, abuse contact, and prefix intelligence."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_STAT_BASE = "https://stat.ripe.net/data"


class RIPEStatScanner(BaseOsintScanner):
    """Queries the free RIPEstat Data API for BGP routing, ASN details, and abuse contacts.

    No API key required. Endpoints used:
    - /prefix-overview/data.json  — ASN, prefix, holder info for IP or prefix
    - /abuse-contact-finder/data.json — abuse contact email for an IP
    - /routing-history/data.json — last 30 days of BGP routing history (hijack detection)

    For DOMAIN inputs the domain is first resolved to an IPv4 address.
    """

    scanner_name = "ripestat"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        ip = input_value

        if input_type == ScanInputType.DOMAIN:
            ip = await self._resolve_domain(input_value)
            if not ip:
                return {
                    "input": input_value,
                    "found": False,
                    "error": f"Could not resolve domain {input_value} to an IP address",
                    "extracted_identifiers": [],
                }

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                prefix_data, abuse_data, routing_data = await asyncio.gather(
                    self._prefix_overview(client, ip),
                    self._abuse_contact(client, ip),
                    self._routing_history(client, ip),
                    return_exceptions=True,
                )
            except Exception as e:
                log.error("RIPEstat concurrent fetch failed", ip=ip, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

        # Handle individual gather exceptions gracefully
        prefix_result: dict[str, Any] = prefix_data if isinstance(prefix_data, dict) else {}
        abuse_result: dict[str, Any] = abuse_data if isinstance(abuse_data, dict) else {}
        routing_result: dict[str, Any] = routing_data if isinstance(routing_data, dict) else {}

        asn = prefix_result.get("asn")
        prefix = prefix_result.get("prefix", "")
        holder = prefix_result.get("holder", "")
        country = prefix_result.get("country", "")
        is_routed = prefix_result.get("is_routed", False)

        abuse_email = abuse_result.get("abuse_email", "")
        routing_history: list[dict[str, Any]] = routing_result.get("routing_history", [])

        identifiers: list[str] = []
        if asn:
            identifiers.append(f"asn:{asn}")
        if abuse_email:
            identifiers.append(f"email:{abuse_email}")

        return {
            "input": input_value,
            "resolved_ip": ip if input_type == ScanInputType.DOMAIN else None,
            "found": bool(asn or prefix),
            "asn": asn,
            "prefix": prefix,
            "holder": holder,
            "country": country,
            "is_routed": is_routed,
            "abuse_email": abuse_email,
            "routing_history": routing_history,
            "routing_history_entries": len(routing_history),
            "extracted_identifiers": identifiers,
        }

    async def _resolve_domain(self, domain: str) -> str | None:
        try:
            loop = asyncio.get_running_loop()
            result = await loop.getaddrinfo(domain, None, family=socket.AF_INET)
            if result:
                return result[0][4][0]
        except Exception as e:
            log.warning("Domain resolution failed for RIPEstat lookup", domain=domain, error=str(e))
        return None

    async def _prefix_overview(self, client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
        resp = await client.get(
            f"{_STAT_BASE}/prefix-overview/data.json",
            params={"resource": ip},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        asns = data.get("asns", [])
        asn = asns[0].get("asn") if asns else None
        holder = asns[0].get("holder", "") if asns else ""

        return {
            "asn": asn,
            "holder": holder,
            "prefix": data.get("resource", ""),
            "country": data.get("block", {}).get("desc", ""),
            "is_routed": data.get("is_less_specific", False) or bool(asns),
        }

    async def _abuse_contact(self, client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
        resp = await client.get(
            f"{_STAT_BASE}/abuse-contact-finder/data.json",
            params={"resource": ip},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        abuse_contacts = data.get("abuse_contacts", [])
        abuse_email = abuse_contacts[0] if abuse_contacts else ""

        return {"abuse_email": abuse_email}

    async def _routing_history(self, client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
        resp = await client.get(
            f"{_STAT_BASE}/routing-history/data.json",
            params={"resource": ip, "starttime": "-30d"},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        history: list[dict[str, Any]] = []
        for entry in data.get("by_origin", []):
            history.append({
                "origin_asn": entry.get("origin"),
                "prefix": entry.get("prefix", ""),
                "timelines": entry.get("timelines", []),
            })

        return {"routing_history": history}
