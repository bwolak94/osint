"""YouTube scanner — channel information lookup."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class YouTubeScanner(BaseOsintScanner):
    scanner_name = "youtube"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 43200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.lstrip("@")
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                f"https://www.youtube.com/@{username}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; OSINTBot/1.0)"},
            )

            if resp.status_code == 404:
                return {"username": username, "found": False, "extracted_identifiers": []}

            found = resp.status_code == 200

            identifiers = [f"username:{username}"]
            if found:
                identifiers.extend([
                    "service:youtube",
                    f"url:https://www.youtube.com/@{username}",
                ])

            return {
                "username": username,
                "found": found,
                "channel_url": f"https://www.youtube.com/@{username}",
                "extracted_identifiers": identifiers,
            }
