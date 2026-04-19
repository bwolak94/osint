"""AlienVault OTX enhanced scanner — multi-indicator threat intelligence lookups."""

from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OTX_BASE = "https://otx.alienvault.com/api/v1"


class OTXScanner(BaseOsintScanner):
    """Queries AlienVault OTX for threat intelligence across multiple indicator types.

    Uses the free OTX community API.  An ``otx_api_key`` in config unlocks
    higher rate limits and access to private pulses, but basic data is
    accessible without a key for IP and domain indicators.

    Supported input types:
    - IP_ADDRESS: general info + malware associations + passive DNS
    - DOMAIN: general + malware + passive DNS + WHOIS
    - URL: general indicator lookup

    Returns:
    - pulse_count, pulse_names: OTX pulse intelligence
    - malware_families: malware families associated with the indicator
    - geolocation: country/city/coordinates
    - passive_dns: historical DNS resolution records
    - whois_data: WHOIS information (DOMAIN only)
    - reputation_score: OTX reputation value
    - tags, attack_ids: MITRE ATT&CK identifiers
    - first_seen, last_seen timestamps

    Passive DNS IP resolutions and associated domains are surfaced as
    extracted identifiers for graph pivoting.
    """

    scanner_name = "otx_enhanced"
    supported_input_types = frozenset({
        ScanInputType.IP_ADDRESS,
        ScanInputType.DOMAIN,
        ScanInputType.URL,
    })
    cache_ttl = 3600

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        api_key = get_settings().otx_api_key
        if api_key:
            headers["X-OTX-API-KEY"] = api_key
        return headers

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        headers = self._build_headers()
        async with httpx.AsyncClient(timeout=20) as client:
            if input_type == ScanInputType.IP_ADDRESS:
                return await self._scan_ip(client, headers, input_value)
            if input_type == ScanInputType.DOMAIN:
                return await self._scan_domain(client, headers, input_value)
            if input_type == ScanInputType.URL:
                return await self._scan_url(client, headers, input_value)
        return {"input": input_value, "found": False, "extracted_identifiers": []}

    async def _fetch(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        path: str,
    ) -> dict[str, Any]:
        """Fetch a single OTX endpoint, returning an empty dict on non-200."""
        resp = await client.get(f"{_OTX_BASE}{path}", headers=headers)
        if resp.status_code == 429:
            from src.adapters.scanners.exceptions import RateLimitError
            raise RateLimitError("OTX rate limit exceeded")
        if resp.status_code != 200:
            log.debug("OTX endpoint returned non-200", path=path, status=resp.status_code)
            return {}
        return resp.json()

    async def _scan_ip(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        ip: str,
    ) -> dict[str, Any]:
        general, malware, pdns = await _gather_three(
            self._fetch(client, headers, f"/indicators/IPv4/{ip}/general"),
            self._fetch(client, headers, f"/indicators/IPv4/{ip}/malware"),
            self._fetch(client, headers, f"/indicators/IPv4/{ip}/passive_dns"),
        )
        return self._build_result(ip, general, malware, pdns, whois={})

    async def _scan_domain(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        domain: str,
    ) -> dict[str, Any]:
        general, malware, pdns, whois = await _gather_four(
            self._fetch(client, headers, f"/indicators/domain/{domain}/general"),
            self._fetch(client, headers, f"/indicators/domain/{domain}/malware"),
            self._fetch(client, headers, f"/indicators/domain/{domain}/passive_dns"),
            self._fetch(client, headers, f"/indicators/domain/{domain}/whois"),
        )
        return self._build_result(domain, general, malware, pdns, whois)

    async def _scan_url(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        url: str,
    ) -> dict[str, Any]:
        encoded = quote(url, safe="")
        general = await self._fetch(client, headers, f"/indicators/url/{encoded}/general")
        return self._build_result(url, general, {}, {}, {})

    def _build_result(
        self,
        input_value: str,
        general: dict[str, Any],
        malware: dict[str, Any],
        pdns: dict[str, Any],
        whois: dict[str, Any],
    ) -> dict[str, Any]:
        if not general:
            return {
                "input": input_value,
                "found": False,
                "extracted_identifiers": [],
            }

        pulse_info = general.get("pulse_info", {}) or {}
        pulses: list[dict[str, Any]] = pulse_info.get("pulses", []) or []
        pulse_names = [p.get("name", "") for p in pulses if p.get("name")]

        # Malware families from malware endpoint
        malware_families: list[str] = []
        for mw in (malware.get("data", []) or []):
            family = mw.get("detections", {}).get("family", "")
            if family and family not in malware_families:
                malware_families.append(family)

        # Passive DNS records and identifier extraction
        passive_dns_records: list[dict[str, Any]] = []
        identifiers: list[str] = []
        for record in (pdns.get("passive_dns", []) or []):
            address = record.get("address", "")
            hostname = record.get("hostname", "")
            passive_dns_records.append({
                "address": address,
                "hostname": hostname,
                "first": record.get("first"),
                "last": record.get("last"),
                "record_type": record.get("record_type"),
            })
            if address:
                ident = f"ip:{address}"
                if ident not in identifiers:
                    identifiers.append(ident)
            if hostname:
                ident = f"domain:{hostname}"
                if ident not in identifiers:
                    identifiers.append(ident)

        # Geolocation
        geo = {
            "country": general.get("country_name"),
            "country_code": general.get("country_code"),
            "city": general.get("city"),
            "latitude": general.get("latitude"),
            "longitude": general.get("longitude"),
            "asn": general.get("asn"),
        }

        # MITRE ATT&CK IDs from pulses
        attack_ids: list[str] = []
        for pulse in pulses:
            for attack in (pulse.get("attack_ids", []) or []):
                aid = attack.get("id", "")
                if aid and aid not in attack_ids:
                    attack_ids.append(aid)

        # Tags aggregated from pulses
        tags: list[str] = []
        for pulse in pulses:
            for tag in (pulse.get("tags", []) or []):
                if tag and tag not in tags:
                    tags.append(tag)

        return {
            "input": input_value,
            "found": True,
            "pulse_count": pulse_info.get("count", len(pulses)),
            "pulse_names": pulse_names,
            "malware_families": malware_families,
            "geolocation": geo,
            "passive_dns": passive_dns_records,
            "whois_data": whois,
            "reputation_score": general.get("reputation", 0),
            "first_seen": general.get("first_seen"),
            "last_seen": general.get("last_seen"),
            "tags": tags,
            "attack_ids": attack_ids,
            "indicator": general.get("indicator"),
            "type": general.get("type"),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


# ---------------------------------------------------------------------------
# asyncio helpers (avoid importing asyncio.gather to keep the module lighter)
# ---------------------------------------------------------------------------

import asyncio


async def _gather_three(
    coro1: Any,
    coro2: Any,
    coro3: Any,
) -> tuple[Any, Any, Any]:
    results = await asyncio.gather(coro1, coro2, coro3, return_exceptions=True)
    return (
        results[0] if not isinstance(results[0], Exception) else {},
        results[1] if not isinstance(results[1], Exception) else {},
        results[2] if not isinstance(results[2], Exception) else {},
    )


async def _gather_four(
    coro1: Any,
    coro2: Any,
    coro3: Any,
    coro4: Any,
) -> tuple[Any, Any, Any, Any]:
    results = await asyncio.gather(coro1, coro2, coro3, coro4, return_exceptions=True)
    return (
        results[0] if not isinstance(results[0], Exception) else {},
        results[1] if not isinstance(results[1], Exception) else {},
        results[2] if not isinstance(results[2], Exception) else {},
        results[3] if not isinstance(results[3], Exception) else {},
    )
