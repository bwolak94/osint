"""Subdomain Enumeration scanner — discovers subdomains via crt.sh and HackerTarget."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20


class SubdomainScanner(BaseOsintScanner):
    """Enumerates subdomains by combining results from crt.sh and HackerTarget."""

    scanner_name = "subdomain"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        subdomains: set[str] = set()
        sources_used: list[str] = []

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            # Source 1: crt.sh Certificate Transparency
            crtsh_subs = await self._query_crtsh(client, input_value)
            if crtsh_subs is not None:
                subdomains.update(crtsh_subs)
                sources_used.append("crt.sh")

            # Source 2: HackerTarget subdomain finder
            ht_subs = await self._query_hackertarget(client, input_value)
            if ht_subs is not None:
                subdomains.update(ht_subs)
                sources_used.append("hackertarget")

        sorted_subdomains = sorted(subdomains)
        identifiers = [f"domain:{sub}" for sub in sorted_subdomains]

        return {
            "domain": input_value,
            "found": bool(sorted_subdomains),
            "subdomains": sorted_subdomains,
            "subdomain_count": len(sorted_subdomains),
            "sources_used": sources_used,
            "extracted_identifiers": identifiers,
        }

    async def _query_crtsh(self, client: httpx.AsyncClient, domain: str) -> set[str] | None:
        """Query crt.sh for subdomains via Certificate Transparency logs."""
        try:
            resp = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{domain}", "output": "json"},
            )

            if resp.status_code == 404:
                return set()

            resp.raise_for_status()
            entries = resp.json()

            results: set[str] = set()
            for entry in entries:
                for field in ("common_name", "name_value"):
                    value = entry.get(field, "")
                    for name in value.split("\n"):
                        name = name.strip().lower()
                        if name and not name.startswith("*") and domain in name:
                            results.add(name)

            return results
        except Exception as exc:
            log.warning("crt.sh query failed", domain=domain, error=str(exc))
            return None

    async def _query_hackertarget(self, client: httpx.AsyncClient, domain: str) -> set[str] | None:
        """Query HackerTarget subdomain finder API."""
        try:
            resp = await client.get(
                "https://api.hackertarget.com/hostsearch/",
                params={"q": domain},
            )

            if resp.status_code == 404:
                return set()

            resp.raise_for_status()
            text = resp.text

            if not text or "error" in text.lower():
                return set()

            results: set[str] = set()
            for line in text.strip().split("\n"):
                parts = line.split(",")
                if parts:
                    subdomain = parts[0].strip().lower()
                    if subdomain and domain in subdomain:
                        results.add(subdomain)

            return results
        except Exception as exc:
            log.warning("HackerTarget query failed", domain=domain, error=str(exc))
            return None
