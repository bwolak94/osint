"""Ransomware Intelligence scanner — check if a domain appears in ransomware victim lists.

Module 60 in the Credential Intelligence domain. Queries public ransomware tracking
databases (ransomwatch) for victim mentions. Teaches about the geopolitics of
ransomware-as-a-service (RaaS) operations.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_RANSOMWATCH_POSTS = "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json"


class RansomwareIntelScanner(BaseOsintScanner):
    """Check if a domain or organization appears in ransomware victim databases.

    Uses the Ransomwatch open-source project (ransomwatch/ransomwatch on GitHub),
    which aggregates victim disclosures from 100+ RaaS groups. No API key required.

    Returns matched victims with group attribution, post date, and site information
    for threat intelligence enrichment.
    """

    scanner_name = "ransomware_intel"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600  # Ransomware posts update frequently

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        # Normalize: strip www, protocol, path
        domain = domain.replace("https://", "").replace("http://", "").split("/")[0].lstrip("www.")
        # Also extract organization name from domain for partial matching
        org_keyword = domain.split(".")[0] if "." in domain else domain

        async with httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "OSINT-Platform/1.0 RansomwareIntel"},
        ) as client:
            try:
                resp = await client.get(_RANSOMWATCH_POSTS)
                if resp.status_code != 200:
                    return {
                        "found": False,
                        "domain": domain,
                        "error": f"Ransomwatch returned {resp.status_code}",
                    }
                posts: list[dict] = resp.json()
            except Exception as exc:
                return {"found": False, "domain": domain, "error": str(exc)}

        # Search for matches
        matches: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for post in posts:
            post_title = str(post.get("post_title", "")).lower()
            post_url = str(post.get("post_url", "")).lower()
            victim = str(post.get("victim", "") or post.get("post_title", "")).lower()

            # Match on domain or org keyword
            is_match = (
                domain in post_title or
                org_keyword in post_title or
                domain in post_url or
                domain in victim
            )

            if is_match and len(org_keyword) >= 4:  # Avoid false positives on very short names
                entry_id = f"{post.get('group_name', '')}:{post_title[:40]}"
                if entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    matches.append({
                        "group": post.get("group_name", "Unknown"),
                        "victim_title": str(post.get("post_title", ""))[:100],
                        "published": str(post.get("discovered", ""))[:10],
                        "website": post.get("website", ""),
                    })

        return {
            "found": len(matches) > 0,
            "domain": domain,
            "total_matches": len(matches),
            "victim_matches": matches[:10],
            "data_source": "ransomwatch (ransomwatch/ransomwatch on GitHub)",
            "note": "Matches may be false positives for short or common domain names. Verify manually.",
        }
