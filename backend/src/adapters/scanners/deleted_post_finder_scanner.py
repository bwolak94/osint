"""Deleted Post Finder scanner — discover removed content via archival databases.

Module 39 in the SOCMINT domain. Queries the Wayback Machine CDX API to find
archived snapshots of social media profile pages, and checks Pushshift (where
available) for deleted Reddit content. Teaches about external data retention
and the permanence of digital footprints.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class DeletedPostFinderScanner(BaseOsintScanner):
    """Find deleted/removed content by querying archival databases.

    Checks:
    1. Wayback Machine CDX API for cached social profile pages
    2. Reddit profile snapshots (via Wayback)
    3. Arctic Shift (open-source Pushshift alternative) for deleted Reddit posts
    """

    scanner_name = "deleted_post_finder"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 7200

    # Social profile URL templates to check in Wayback
    _PROFILE_TEMPLATES: list[tuple[str, str]] = [
        ("Reddit", "https://www.reddit.com/user/{username}"),
        ("Twitter/X", "https://twitter.com/{username}"),
        ("Instagram", "https://www.instagram.com/{username}/"),
        ("GitHub", "https://github.com/{username}"),
        ("TikTok", "https://www.tiktok.com/@{username}"),
    ]

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip().lstrip("@")
        wayback_snapshots: list[dict[str, Any]] = []
        arctic_shift_results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": "OSINT-Platform/1.0 DeletedPostFinder"},
            follow_redirects=True,
        ) as client:
            # --- Wayback Machine CDX API ---
            for platform, url_template in self._PROFILE_TEMPLATES:
                url = url_template.format(username=username)
                try:
                    cdx_resp = await client.get(
                        "https://web.archive.org/cdx/search/cdx",
                        params={
                            "url": url,
                            "output": "json",
                            "limit": 5,
                            "fl": "timestamp,original,statuscode,mimetype",
                            "filter": "statuscode:200",
                            "collapse": "timestamp:8",  # Collapse to daily
                        },
                    )
                    if cdx_resp.status_code == 200:
                        rows = cdx_resp.json()
                        if rows and len(rows) > 1:  # First row is header
                            for row in rows[1:]:
                                if len(row) >= 4:
                                    ts = row[0]
                                    wayback_snapshots.append({
                                        "platform": platform,
                                        "url": row[1],
                                        "wayback_url": f"https://web.archive.org/web/{ts}/{row[1]}",
                                        "timestamp": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}",
                                        "status_code": row[2],
                                    })
                except Exception as exc:
                    log.debug("deleted_post_finder: wayback CDX failed", platform=platform, error=str(exc))

            # --- Arctic Shift (open Pushshift alternative for Reddit) ---
            try:
                arctic_resp = await client.get(
                    "https://arctic-shift.photon-reddit.com/api/posts/search",
                    params={"author": username, "limit": 10, "sort": "desc"},
                )
                if arctic_resp.status_code == 200:
                    data = arctic_resp.json()
                    for post in data.get("data", [])[:10]:
                        if post.get("removed_by_category") or post.get("selftext") == "[removed]":
                            arctic_shift_results.append({
                                "title": post.get("title", "")[:100],
                                "subreddit": post.get("subreddit", ""),
                                "created_utc": post.get("created_utc"),
                                "removal_reason": post.get("removed_by_category", "unknown"),
                                "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                            })
            except Exception as exc:
                log.debug("deleted_post_finder: arctic shift failed", error=str(exc))

        found = len(wayback_snapshots) > 0 or len(arctic_shift_results) > 0

        return {
            "found": found,
            "username": username,
            "wayback_snapshots": wayback_snapshots,
            "total_wayback_snapshots": len(wayback_snapshots),
            "deleted_reddit_posts": arctic_shift_results,
            "total_deleted_posts": len(arctic_shift_results),
            "note": "Wayback snapshots show cached versions of profile pages. Deleted posts sourced from Arctic Shift (Pushshift alternative).",
        }
