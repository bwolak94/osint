"""Traceroute scanner — traces the network path to a target using HackerTarget MTR API."""

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_HACKERTARGET_MTR = "https://api.hackertarget.com/mtr/"
_IPAPI_URL = "https://ipapi.co/{ip}/json/"

# Regex to parse MTR-style output: hop_num  ip/hostname  rtt
_HOP_RE = re.compile(
    r"^\s*(\d+)\.\s+(?:\|\-\-\s*)?([^\s]+)\s+(\d+(?:\.\d+)?)\s*ms",
    re.MULTILINE,
)


async def _geolocate_ip(client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
    try:
        resp = await client.get(_IPAPI_URL.format(ip=ip), timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "country": data.get("country_name"),
                "city": data.get("city"),
                "asn": data.get("asn"),
                "org": data.get("org"),
            }
    except Exception:
        pass
    return {"country": None, "city": None, "asn": None, "org": None}


class TracerouteScanner(BaseOsintScanner):
    """Traces the network path to a target and enriches hops with geolocation."""

    scanner_name = "traceroute"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        raw_output = ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(_HACKERTARGET_MTR, params={"q": input_value})
                if resp.status_code == 200:
                    raw_output = resp.text
        except Exception as exc:
            log.warning("traceroute MTR request failed", error=str(exc))
            return {
                "target": input_value,
                "found": False,
                "hops": [],
                "total_hops": 0,
                "destination_reached": False,
                "error": str(exc),
                "extracted_identifiers": [],
            }

        hops_raw: list[tuple[str, str, str]] = _HOP_RE.findall(raw_output)

        enriched_hops: list[dict[str, Any]] = []
        ip_set: set[str] = set()

        async with httpx.AsyncClient(timeout=10) as geo_client:
            geo_tasks = []
            for num, host, rtt in hops_raw:
                # Attempt to determine if host is an IP or hostname
                ip_re = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
                ip = host if ip_re.match(host) else None
                geo_tasks.append((num, host, rtt, ip))

            geo_results = await asyncio.gather(
                *[
                    _geolocate_ip(geo_client, item[3]) if item[3] else asyncio.coroutine(lambda: {})()
                    for item in geo_tasks
                ],
                return_exceptions=True,
            )

            for (num, host, rtt, ip), geo in zip(geo_tasks, geo_results):
                geo_data = geo if isinstance(geo, dict) else {}
                hop = {
                    "hop_num": int(num),
                    "ip": ip or host,
                    "hostname": host if not re.match(r"^\d", host) else None,
                    "rtt_ms": float(rtt),
                    **geo_data,
                }
                enriched_hops.append(hop)
                if ip:
                    ip_set.add(ip)

        destination_reached = bool(
            enriched_hops and (
                input_value in (enriched_hops[-1].get("ip", "") or "") or
                input_value in (enriched_hops[-1].get("hostname", "") or "")
            )
        )

        identifiers = [f"ip:{ip}" for ip in ip_set]

        return {
            "target": input_value,
            "found": len(enriched_hops) > 0,
            "hops": enriched_hops,
            "total_hops": len(enriched_hops),
            "destination_reached": destination_reached,
            "raw_output": raw_output[:2000],
            "extracted_identifiers": identifiers,
        }
