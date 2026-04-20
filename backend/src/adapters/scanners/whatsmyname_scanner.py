"""WhatsMyName scanner — community-driven username presence across hundreds of sites."""

import asyncio
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_WMN_DATA_URL = (
    "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
)


class WhatsmynameScanner(BaseOsintScanner):
    scanner_name = "whatsmyname"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip()

        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        ) as client:
            wmn_data = await self._fetch_wmn_data(client)
            sites: list[dict[str, Any]] = wmn_data.get("sites", [])

            found_accounts: list[dict[str, str]] = []
            semaphore = asyncio.Semaphore(30)

            async def check_site(site: dict[str, Any]) -> None:
                name: str = site.get("name", "")
                uri_check: str = site.get("uri_check", "")
                existence_code: int = site.get("account_existence_code", 200)
                category: str = site.get("category", "")

                if not uri_check:
                    return

                url = uri_check.replace("{account}", username)
                async with semaphore:
                    try:
                        resp = await client.get(url, timeout=10)
                        if resp.status_code == existence_code:
                            found_accounts.append(
                                {"name": name, "url": url, "category": category}
                            )
                    except Exception:
                        pass

            await asyncio.gather(*[check_site(s) for s in sites])

        categories_found = sorted({a["category"] for a in found_accounts if a["category"]})
        identifiers = [f"url:{a['url']}" for a in found_accounts]

        return {
            "username": username,
            "found_accounts": found_accounts,
            "total_checked": len(sites),
            "found_count": len(found_accounts),
            "categories_found": categories_found,
            "extracted_identifiers": identifiers,
        }

    async def _fetch_wmn_data(self, client: httpx.AsyncClient) -> dict[str, Any]:
        resp = await client.get(_WMN_DATA_URL, timeout=20)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
