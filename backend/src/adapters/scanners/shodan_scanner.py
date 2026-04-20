"""Shodan scanner — queries Shodan for open ports, services, and vulnerabilities."""

import asyncio
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class ShodanScanner(BaseOsintScanner):
    """Queries the Shodan API for host intelligence (ports, services, vulns).

    When an API key is configured, uses the full Shodan Host API.
    Otherwise falls back to the free InternetDB endpoint (no key required).
    """

    scanner_name = "shodan"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        ip = input_value

        # If the input is a domain, resolve it to an IP first
        if input_type == ScanInputType.DOMAIN:
            ip = await self._resolve_domain(input_value)
            if not ip:
                return {
                    "input": input_value,
                    "found": False,
                    "error": f"Could not resolve domain {input_value} to an IP address",
                    "extracted_identifiers": [],
                }

        settings = get_settings()
        api_key = settings.shodan_api_key

        if api_key:
            return await self._query_shodan_api(ip, api_key, input_value)
        else:
            return await self._query_internetdb(ip, input_value)

    async def _resolve_domain(self, domain: str) -> str | None:
        """Resolve a domain to its first A-record IP address."""
        try:
            loop = asyncio.get_running_loop()
            result = await loop.getaddrinfo(domain, None, family=socket.AF_INET)
            if result:
                return result[0][4][0]
        except Exception as e:
            log.warning("Domain resolution failed", domain=domain, error=str(e))
        return None

    async def _query_shodan_api(self, ip: str, api_key: str, original_input: str) -> dict[str, Any]:
        """Query the full Shodan Host API (requires API key)."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.shodan.io/shodan/host/{ip}",
                params={"key": api_key},
            )

            if resp.status_code == 404:
                return {
                    "input": original_input,
                    "ip": ip,
                    "found": False,
                    "source": "shodan_api",
                    "extracted_identifiers": [],
                }

            resp.raise_for_status()
            data = resp.json()

        ports = data.get("ports", [])
        vulns = data.get("vulns", [])
        hostnames = data.get("hostnames", [])
        os_name = data.get("os")
        isp = data.get("isp")
        country = data.get("country_name")

        # Collect unique service names from banners
        services: list[str] = []
        for item in data.get("data", []):
            product = item.get("product")
            if product and product not in services:
                services.append(product)

        identifiers: list[str] = []
        for port in ports:
            identifiers.append(f"port:{port}")
        for service in services:
            identifiers.append(f"service:{service}")
        for vuln in vulns:
            identifiers.append(f"vuln:{vuln}")
        for hostname in hostnames:
            identifiers.append(f"domain:{hostname}")

        return {
            "input": original_input,
            "ip": ip,
            "found": True,
            "source": "shodan_api",
            "ports": ports,
            "services": services,
            "vulns": vulns,
            "hostnames": hostnames,
            "os": os_name,
            "isp": isp,
            "country": country,
            "extracted_identifiers": identifiers,
        }

    async def _query_internetdb(self, ip: str, original_input: str) -> dict[str, Any]:
        """Query the free Shodan InternetDB endpoint (no API key needed)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://internetdb.shodan.io/{ip}")

            if resp.status_code == 404:
                return {
                    "input": original_input,
                    "ip": ip,
                    "found": False,
                    "source": "internetdb",
                    "note": "No Shodan API key configured; using free InternetDB endpoint",
                    "extracted_identifiers": [],
                }

            resp.raise_for_status()
            data = resp.json()

        ports = data.get("ports", [])
        vulns = data.get("vulns", [])
        hostnames = data.get("hostnames", [])
        cpes = data.get("cpes", [])

        identifiers: list[str] = []
        for port in ports:
            identifiers.append(f"port:{port}")
        for vuln in vulns:
            identifiers.append(f"vuln:{vuln}")
        for hostname in hostnames:
            identifiers.append(f"domain:{hostname}")

        return {
            "input": original_input,
            "ip": ip,
            "found": True,
            "source": "internetdb",
            "note": "No Shodan API key configured; using free InternetDB endpoint",
            "ports": ports,
            "vulns": vulns,
            "hostnames": hostnames,
            "cpes": cpes,
            "extracted_identifiers": identifiers,
        }
