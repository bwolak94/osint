"""InternetDB scanner — Shodan's free IP intelligence endpoint (no API key required)."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class InternetDBScanner(BaseOsintScanner):
    """Queries Shodan's free InternetDB endpoint for open ports, CPEs, hostnames, tags, and CVEs.

    No API key required. Data is updated weekly by Shodan's continuous scanning infrastructure.
    Rate limit: reasonable use; no hard published limit for single IPs.
    """

    scanner_name = "internetdb"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 43200  # 12 hours — data updates weekly, but cache for half a day to avoid hammering

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(f"https://internetdb.shodan.io/{input_value}")

                if resp.status_code == 404:
                    return {
                        "input": input_value,
                        "found": False,
                        "open_ports": [],
                        "cpes": [],
                        "hostnames": [],
                        "tags": [],
                        "vulns": [],
                        "extracted_identifiers": [],
                    }

                resp.raise_for_status()
                data = resp.json()

            except httpx.HTTPStatusError as e:
                log.warning("InternetDB HTTP error", ip=input_value, status=e.response.status_code)
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }
            except Exception as e:
                log.error("InternetDB scan failed", ip=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

        open_ports: list[int] = data.get("ports", [])
        cpes: list[str] = data.get("cpes", [])
        hostnames: list[str] = data.get("hostnames", [])
        tags: list[str] = data.get("tags", [])
        vulns: list[str] = data.get("vulns", [])

        identifiers: list[str] = []
        for hostname in hostnames:
            identifiers.append(f"domain:{hostname}")
        for cve in vulns:
            identifiers.append(f"vuln:{cve}")

        return {
            "input": input_value,
            "found": True,
            "ip": data.get("ip", input_value),
            "open_ports": open_ports,
            "cpes": cpes,
            "hostnames": hostnames,
            "tags": tags,
            "vulns": vulns,
            "extracted_identifiers": identifiers,
        }
