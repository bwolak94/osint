"""HackerTarget scanner — free DNS, reverse IP, and subdomain lookup endpoints."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://api.hackertarget.com"


class HackerTargetScanner(BaseOsintScanner):
    """Queries HackerTarget free API endpoints for DNS records, subdomains, and reverse-IP data.

    No API key required for free tier (rate-limited by IP).
    - DOMAIN: hostsearch (subdomains+IPs) + dnslookup (DNS records)
    - IP_ADDRESS: reverseiplookup (co-hosted domains)
    """

    scanner_name = "hackertarget"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                if input_type == ScanInputType.DOMAIN:
                    return await self._scan_domain(client, input_value)
                return await self._scan_ip(client, input_value)
            except Exception as e:
                log.error("HackerTarget scan failed", input=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

    async def _scan_domain(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        identifiers: list[str] = []
        subdomains: list[dict[str, str]] = []
        dns_records: list[str] = []

        # 1. Host search — subdomains + IPs
        try:
            resp = await client.get(f"{_BASE_URL}/hostsearch/", params={"q": domain})
            resp.raise_for_status()
            raw_hosts = resp.text.strip()
            if raw_hosts and not raw_hosts.lower().startswith("error"):
                for line in raw_hosts.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(",", 1)
                    entry: dict[str, str] = {"subdomain": parts[0].strip()}
                    if len(parts) == 2:
                        entry["ip"] = parts[1].strip()
                        identifiers.append(f"ip:{parts[1].strip()}")
                    identifiers.append(f"domain:{parts[0].strip()}")
                    subdomains.append(entry)
        except Exception as e:
            log.warning("HackerTarget hostsearch failed", domain=domain, error=str(e))

        # 2. DNS lookup — A, MX, NS, TXT records
        try:
            resp = await client.get(f"{_BASE_URL}/dnslookup/", params={"q": domain})
            resp.raise_for_status()
            raw_dns = resp.text.strip()
            if raw_dns and not raw_dns.lower().startswith("error"):
                dns_records = [line.strip() for line in raw_dns.splitlines() if line.strip()]
        except Exception as e:
            log.warning("HackerTarget dnslookup failed", domain=domain, error=str(e))

        return {
            "input": domain,
            "found": bool(subdomains or dns_records),
            "subdomains": subdomains,
            "dns_records": dns_records,
            "extracted_identifiers": identifiers,
        }

    async def _scan_ip(self, client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
        identifiers: list[str] = []
        co_hosted_domains: list[str] = []

        try:
            resp = await client.get(f"{_BASE_URL}/reverseiplookup/", params={"q": ip})
            resp.raise_for_status()
            raw = resp.text.strip()
            if raw and not raw.lower().startswith("error"):
                for line in raw.splitlines():
                    domain = line.strip()
                    if domain:
                        co_hosted_domains.append(domain)
                        identifiers.append(f"domain:{domain}")
        except Exception as e:
            log.warning("HackerTarget reverseiplookup failed", ip=ip, error=str(e))
            return {
                "input": ip,
                "found": False,
                "error": str(e),
                "extracted_identifiers": [],
            }

        return {
            "input": ip,
            "found": bool(co_hosted_domains),
            "co_hosted_domains": co_hosted_domains,
            "co_hosted_count": len(co_hosted_domains),
            "extracted_identifiers": identifiers,
        }
