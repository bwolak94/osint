"""BeVigil scanner — mobile intelligence for domain/subdomain and URL discovery from APKs."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://osint.bevigil.com/api"


class BeVigilScanner(BaseOsintScanner):
    scanner_name = "bevigil"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        settings = get_settings()
        api_key = settings.bevigil_api_key if hasattr(settings, "bevigil_api_key") else ""

        headers: dict[str, str] = {"User-Agent": "OSINT-Platform/1.0"}
        if api_key:
            headers["X-Access-Token"] = api_key

        subdomains: list[str] = []
        urls_in_apps: list[str] = []
        parameters: list[str] = []
        app_count = 0
        leaks_found: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            subdomains = await self._fetch_subdomains(client, domain, headers)
            urls_in_apps = await self._fetch_urls(client, domain, headers)
            parameters = await self._fetch_parameters(client, domain, headers)

        identifiers: list[str] = []
        for sub in subdomains:
            identifiers.append(f"domain:{sub}")
        for url in urls_in_apps[:20]:
            identifiers.append(f"url:{url}")

        return {
            "domain": domain,
            "subdomains_from_apps": subdomains,
            "urls_in_apps": urls_in_apps,
            "parameters": parameters,
            "app_count": app_count,
            "leaks_found": leaks_found,
            "extracted_identifiers": list(dict.fromkeys(identifiers)),
        }

    async def _fetch_subdomains(
        self, client: httpx.AsyncClient, domain: str, headers: dict[str, str]
    ) -> list[str]:
        try:
            resp = await client.get(f"{_BASE_URL}/{domain}/subdomains/", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    raw = data.get("subdomains", data.get("data", []))
                elif isinstance(data, list):
                    raw = data
                else:
                    raw = []
                return [str(s) for s in raw if s]
        except Exception as exc:
            log.debug("BeVigil subdomains failed", domain=domain, error=str(exc))
        return []

    async def _fetch_urls(
        self, client: httpx.AsyncClient, domain: str, headers: dict[str, str]
    ) -> list[str]:
        try:
            resp = await client.get(f"{_BASE_URL}/{domain}/urls/", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    raw = data.get("urls", data.get("data", []))
                elif isinstance(data, list):
                    raw = data
                else:
                    raw = []
                return [str(u) for u in raw if u]
        except Exception as exc:
            log.debug("BeVigil URLs failed", domain=domain, error=str(exc))
        return []

    async def _fetch_parameters(
        self, client: httpx.AsyncClient, domain: str, headers: dict[str, str]
    ) -> list[str]:
        try:
            resp = await client.get(f"{_BASE_URL}/{domain}/parameters/", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    raw = data.get("parameters", data.get("data", []))
                elif isinstance(data, list):
                    raw = data
                else:
                    raw = []
                return [str(p) for p in raw if p]
        except Exception as exc:
            log.debug("BeVigil parameters failed", domain=domain, error=str(exc))
        return []
