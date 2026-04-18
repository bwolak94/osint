"""TikTok scanner — public profile information lookup."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class TikTokScanner(BaseOsintScanner):
    scanner_name = "tiktok"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 21600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.lstrip("@")
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                f"https://www.tiktok.com/@{username}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; OSINTBot/1.0)"},
            )

            if resp.status_code == 404:
                return {"username": username, "found": False, "extracted_identifiers": []}

            found = resp.status_code == 200 and f"@{username}" in resp.text.lower()

            identifiers = [f"username:{username}"]
            if found:
                identifiers.extend([
                    "service:tiktok",
                    f"url:https://www.tiktok.com/@{username}",
                ])

            return {
                "username": username,
                "found": found,
                "profile_url": f"https://www.tiktok.com/@{username}",
                "extracted_identifiers": identifiers,
            }
