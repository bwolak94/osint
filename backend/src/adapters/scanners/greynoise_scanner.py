"""GreyNoise scanner — classifies IP addresses as mass scanners, benign services, or malicious."""

from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_GREYNOISE_BASE = "https://api.greynoise.io/v3"
_INTERNETDB_BASE = "https://internetdb.shodan.io"


class GreyNoiseScanner(BaseOsintScanner):
    """Classifies IP addresses using the GreyNoise Community API.

    With a valid ``greynoise_api_key`` in config, the scanner queries the
    GreyNoise Community endpoint and enriched GNQL stats endpoint.  Without a
    key it falls back to the InternetDB (Shodan) free API which provides tag
    data usable as a lightweight substitute.

    Returns noise/riot classification, malicious/benign/unknown verdict,
    named service info, and last-seen timestamp.
    """

    scanner_name = "greynoise"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 3600

    def _api_key(self) -> str:
        return get_settings().greynoise_api_key

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        api_key = self._api_key()
        if api_key:
            return await self._query_greynoise(input_value, api_key)
        return await self._query_internetdb_fallback(input_value)

    async def _query_greynoise(self, ip: str, api_key: str) -> dict[str, Any]:
        headers = {"key": api_key, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            community_resp = await client.get(
                f"{_GREYNOISE_BASE}/community/{ip}",
                headers=headers,
            )

            result: dict[str, Any] = {
                "input": ip,
                "found": False,
                "source": "greynoise",
                "extracted_identifiers": [],
            }

            if community_resp.status_code == 404:
                result["message"] = "IP not observed by GreyNoise"
                return result

            if community_resp.status_code == 429:
                from src.adapters.scanners.exceptions import RateLimitError
                raise RateLimitError("GreyNoise rate limit exceeded")

            if community_resp.status_code != 200:
                log.warning(
                    "GreyNoise community API error",
                    status=community_resp.status_code,
                    ip=ip,
                )
                return result

            data = community_resp.json()
            result.update({
                "found": True,
                "noise": data.get("noise", False),
                "riot": data.get("riot", False),
                "classification": data.get("classification", "unknown"),
                "name": data.get("name", ""),
                "link": data.get("link", ""),
                "last_seen": data.get("last_seen", ""),
                "message": data.get("message", ""),
            })

            # Enriched GNQL stats (best-effort — non-fatal on error)
            try:
                encoded_query = quote(f"ip:{ip}")
                stats_resp = await client.get(
                    f"{_GREYNOISE_BASE}/gnql/stats",
                    params={"query": f"ip:{ip}"},
                    headers=headers,
                )
                if stats_resp.status_code == 200:
                    stats = stats_resp.json()
                    result["gnql_stats"] = {
                        "count": stats.get("count", 0),
                        "complete": stats.get("complete", False),
                        "message": stats.get("message", ""),
                    }
            except Exception as exc:
                log.debug("GreyNoise GNQL stats fetch failed (non-fatal)", error=str(exc), ip=ip)

        return result

    async def _query_internetdb_fallback(self, ip: str) -> dict[str, Any]:
        """Fall back to InternetDB (Shodan free tier) when no GreyNoise key is present."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_INTERNETDB_BASE}/{ip}")

        result: dict[str, Any] = {
            "input": ip,
            "found": False,
            "source": "internetdb_fallback",
            "extracted_identifiers": [],
        }

        if resp.status_code == 404:
            result["message"] = "IP not found in InternetDB"
            return result

        if resp.status_code != 200:
            return result

        data = resp.json()
        tags: list[str] = data.get("tags", [])
        result.update({
            "found": True,
            "noise": bool(tags),
            "riot": False,
            "classification": "unknown",
            "name": "",
            "link": f"https://internetdb.shodan.io/{ip}",
            "last_seen": "",
            "message": "",
            "internetdb_tags": tags,
            "open_ports": data.get("ports", []),
            "hostnames": data.get("hostnames", []),
            "cpes": data.get("cpes", []),
            "vulns": data.get("vulns", []),
        })
        return result
