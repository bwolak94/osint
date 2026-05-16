"""Shodan bulk IP enrichment scanner.

Uses Shodan InternetDB (free, no API key) and Shodan API (if configured) to:
- Bulk enrich IPs extracted from investigation data
- Find open ports and services per IP
- Map CVEs associated with identified services
- Identify hosting providers and ASNs
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_IP_RE = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
)
_PRIVATE_RANGES = re.compile(
    r'^(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.|127\.|169\.254\.|::1$|fc|fd)'
)
_INTERNETDB = "https://internetdb.shodan.io"


class ShodanBulkScanner(BaseOsintScanner):
    """Shodan InternetDB bulk IP enrichment scanner (no API key required)."""

    scanner_name = "shodan_bulk"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS,
                                        ScanInputType.EMAIL})
    cache_ttl = 14400
    scan_timeout = 45

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        # Extract IPs from input (could be a single IP or text with embedded IPs)
        if input_type == ScanInputType.IP_ADDRESS and _IP_RE.match(query.strip()):
            ips = [query.strip()]
        else:
            ips = _IP_RE.findall(query)

        # Filter private IPs
        public_ips = [ip for ip in ips if not _PRIVATE_RANGES.match(ip)]
        # Limit to 10 IPs per scan
        public_ips = list(dict.fromkeys(public_ips))[:10]

        if not public_ips:
            # Try resolving domain to IP
            if input_type == ScanInputType.DOMAIN:
                try:
                    import socket
                    resolved = socket.gethostbyname(query.split("/")[0])
                    if resolved and not _PRIVATE_RANGES.match(resolved):
                        public_ips = [resolved]
                except Exception:
                    pass

        if not public_ips:
            return {
                "input": query,
                "scan_mode": "manual_fallback",
                "findings": [],
                "total_found": 0,
                "note": "No public IPs found in input",
                "extracted_identifiers": [],
            }

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ShodanBulkScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(5)

            async def enrich_ip(ip: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_INTERNETDB}/{ip}",
                            timeout=6,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)

                            ports = data.get("ports", [])
                            cves = data.get("vulns", [])
                            tags = data.get("tags", [])
                            hostnames = data.get("hostnames", [])
                            org = data.get("org", "")

                            severity = "critical" if cves else ("high" if ports else "info")
                            identifiers.append(f"{severity}:shodan:{ip}")
                            findings.append({
                                "type": "ip_enrichment",
                                "severity": severity,
                                "source": "Shodan InternetDB",
                                "ip": ip,
                                "open_ports": ports,
                                "cves": cves[:10],
                                "cve_count": len(cves),
                                "tags": tags,
                                "hostnames": hostnames[:5],
                                "org": org,
                                "description": (
                                    f"Shodan {ip}: {len(ports)} open ports"
                                    + (f", {len(cves)} CVEs" if cves else "")
                                    + (f" — {org}" if org else "")
                                ),
                            })
                        elif resp.status_code == 404:
                            # IP not in Shodan database, still record it
                            findings.append({
                                "type": "ip_enrichment",
                                "severity": "info",
                                "source": "Shodan InternetDB",
                                "ip": ip,
                                "open_ports": [],
                                "cves": [],
                                "description": f"Shodan: {ip} — not indexed",
                            })
                    except Exception as exc:
                        log.debug("Shodan InternetDB error", ip=ip, error=str(exc))

            await asyncio.gather(*[enrich_ip(ip) for ip in public_ips])

        # Aggregate summary
        total_cves = sum(f.get("cve_count", 0) for f in findings)
        critical_ips = [f["ip"] for f in findings if f.get("cves")]
        if findings:
            findings.insert(0, {
                "type": "shodan_bulk_summary",
                "severity": "critical" if total_cves > 0 else "info",
                "source": "Shodan InternetDB",
                "ips_scanned": len(public_ips),
                "total_cves": total_cves,
                "vulnerable_ips": critical_ips,
                "description": (
                    f"Shodan bulk: {len(public_ips)} IPs scanned, {total_cves} CVEs found"
                    + (f" — {len(critical_ips)} vulnerable IPs" if critical_ips else "")
                ),
            })

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "ips_scanned": public_ips,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
