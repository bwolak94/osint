"""Reddit scanner — public user profile lookup."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class RedditScanner(BaseOsintScanner):
    scanner_name = "reddit"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 21600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.lstrip("u/").lstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://www.reddit.com/user/{username}/about.json",
                headers={"User-Agent": "OSINT-Platform/1.0"},
            )

            if resp.status_code == 404:
                return {"username": username, "found": False, "extracted_identifiers": []}

            if resp.status_code != 200:
                return {
                    "username": username,
                    "found": False,
                    "error": f"HTTP {resp.status_code}",
                    "extracted_identifiers": [],
                }

            data = resp.json().get("data", {})
            identifiers = [f"username:{username}", "service:reddit"]

            return {
                "username": username,
                "found": True,
                "display_name": data.get("subreddit", {}).get(
                    "display_name_prefixed", f"u/{username}"
                ),
                "comment_karma": data.get("comment_karma", 0),
                "link_karma": data.get("link_karma", 0),
                "created_utc": data.get("created_utc"),
                "is_verified": data.get("verified", False),
                "has_verified_email": data.get("has_verified_email", False),
                "profile_url": f"https://www.reddit.com/user/{username}",
                "extracted_identifiers": identifiers,
            }
