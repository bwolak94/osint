"""BGP hijack scanner — detects routing anomalies via RIPE RIS data."""

import asyncio
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20
_RIPE_BASE = "https://stat.ripe.net/data"


class BGPHijackScanner(BaseOsintScanner):
    """Queries RIPE RIS to surface BGP routing anomalies such as multiple ASNs
    announcing the same prefix or unexpected origin changes."""

    scanner_name = "bgp_hijack"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN})
    cache_ttl = 3600  # 1 hour — routing data changes frequently

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            if input_type == ScanInputType.DOMAIN:
                ip = await self._resolve_domain(input_value)
                if ip is None:
                    return {
                        "input": input_value,
                        "found": False,
                        "error": f"Could not resolve domain: {input_value}",
                        "extracted_identifiers": [],
                    }
                resource = ip
            else:
                resource = input_value

            routing_history, prefix, seen_asns = await self._fetch_routing_history(client, resource)
            announced_prefixes: list[str] = []

            # If we found an origin ASN, also pull its full prefix advertisement list
            primary_asn: str | None = seen_asns[0] if seen_asns else None
            if primary_asn:
                announced_prefixes = await self._fetch_announced_prefixes(client, primary_asn)

            hijack_detected, anomalies = self._detect_anomalies(seen_asns, routing_history)

            identifiers: list[str] = [f"asn:{asn}" for asn in seen_asns]
            # Flag suspicious secondary origins as IP-based identifiers (best proxy available)
            if hijack_detected and len(seen_asns) > 1:
                for asn in seen_asns[1:]:
                    identifiers.append(f"asn:{asn}")

            return {
                "input": input_value,
                "resource": resource,
                "found": bool(routing_history),
                "prefix": prefix,
                "expected_asn": primary_asn,
                "actual_asns": seen_asns,
                "hijack_detected": hijack_detected,
                "anomalies": anomalies,
                "routing_history": routing_history,
                "announced_prefixes": announced_prefixes,
                "extracted_identifiers": identifiers,
            }

    async def _resolve_domain(self, domain: str) -> str | None:
        """Resolve a domain name to an IPv4 address."""
        try:
            loop = asyncio.get_running_loop()
            results = await loop.getaddrinfo(domain, None, family=socket.AF_INET)
            if results:
                return results[0][4][0]
        except Exception as exc:
            log.warning("Domain resolution failed", domain=domain, error=str(exc))
        return None

    async def _fetch_routing_history(
        self,
        client: httpx.AsyncClient,
        resource: str,
    ) -> tuple[list[dict[str, Any]], str, list[str]]:
        """Retrieve routing history for an IP address or prefix from RIPE RIS."""
        url = f"{_RIPE_BASE}/routing-history/data.json"
        try:
            resp = await client.get(url, params={"resource": resource})

            if resp.status_code == 429:
                raise RateLimitError("RIPE Stat API rate limited")
            if resp.status_code != 200:
                log.warning("RIPE routing-history unexpected status", status=resp.status_code, resource=resource)
                return [], "", []

            payload = resp.json()
            data = payload.get("data", {})
            by_origin: list[dict[str, Any]] = data.get("by_origin", [])
            prefix: str = data.get("resource", resource)

            seen_asns: list[str] = []
            history_records: list[dict[str, Any]] = []

            for origin_block in by_origin:
                asn = str(origin_block.get("origin", ""))
                if asn and asn not in seen_asns:
                    seen_asns.append(asn)

                for interval in origin_block.get("prefixes", []):
                    history_records.append(
                        {
                            "asn": asn,
                            "prefix": interval.get("prefix", ""),
                            "timelines": interval.get("timelines", []),
                        }
                    )

            return history_records, prefix, seen_asns

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("RIPE routing-history query failed", resource=resource, error=str(exc))
            return [], "", []

    async def _fetch_announced_prefixes(
        self,
        client: httpx.AsyncClient,
        asn: str,
    ) -> list[str]:
        """Fetch the current set of prefixes announced by a given ASN."""
        url = f"{_RIPE_BASE}/announced-prefixes/data.json"
        try:
            resp = await client.get(url, params={"resource": f"AS{asn}"})

            if resp.status_code == 429:
                raise RateLimitError("RIPE Stat API rate limited")
            if resp.status_code != 200:
                return []

            payload = resp.json()
            prefixes_data: list[dict[str, Any]] = payload.get("data", {}).get("prefixes", [])
            return [p.get("prefix", "") for p in prefixes_data if p.get("prefix")]

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("RIPE announced-prefixes query failed", asn=asn, error=str(exc))
            return []

    def _detect_anomalies(
        self,
        seen_asns: list[str],
        routing_history: list[dict[str, Any]],
    ) -> tuple[bool, list[str]]:
        """Analyse routing history for known BGP hijack signals.

        Current heuristics:
        - Multiple distinct ASNs have announced the same prefix.
        - The origin ASN changed across different timeline intervals.
        """
        anomalies: list[str] = []

        if len(seen_asns) > 1:
            anomalies.append(
                f"Multiple ASNs ({', '.join(seen_asns)}) have announced the same prefix — "
                "possible hijack or MOAS (Multiple Origin AS) event."
            )

        # Look for timeline gaps or origin changes within a single prefix record
        for record in routing_history:
            timelines: list[dict[str, Any]] = record.get("timelines", [])
            if len(timelines) > 2:
                anomalies.append(
                    f"Prefix {record.get('prefix')} from ASN {record.get('asn')} "
                    f"has {len(timelines)} distinct timeline windows — potential route flapping."
                )

        hijack_detected = bool(anomalies)
        return hijack_detected, anomalies
