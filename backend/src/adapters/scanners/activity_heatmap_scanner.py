"""Activity Heatmap scanner — analyze user posting timestamps for pattern-of-life intelligence.

Module 25 in the SOCMINT domain. Queries Reddit's public JSON API to collect post/comment
timestamps and builds an activity distribution map that can reveal timezone and daily routines.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class ActivityHeatmapScanner(BaseOsintScanner):
    """Analyze user activity timestamps to build a pattern-of-life heatmap.

    Uses Reddit's public JSON API (no key required) to collect up to 100 recent
    posts/comments and computes hour-of-day and day-of-week frequency distributions.
    """

    scanner_name = "activity_heatmap"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip().lstrip("@")
        timestamps: list[int] = []

        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "OSINT-Platform/1.0 ActivityHeatmap"},
        ) as client:
            # Collect post timestamps
            try:
                posts_resp = await client.get(
                    f"https://www.reddit.com/user/{username}/submitted.json",
                    params={"limit": 100},
                )
                if posts_resp.status_code == 200:
                    data = posts_resp.json()
                    for item in data.get("data", {}).get("children", []):
                        ts = item.get("data", {}).get("created_utc")
                        if ts:
                            timestamps.append(int(ts))
            except Exception as exc:
                log.debug("activity_heatmap: posts fetch failed", error=str(exc))

            # Collect comment timestamps
            try:
                comments_resp = await client.get(
                    f"https://www.reddit.com/user/{username}/comments.json",
                    params={"limit": 100},
                )
                if comments_resp.status_code == 200:
                    data = comments_resp.json()
                    for item in data.get("data", {}).get("children", []):
                        ts = item.get("data", {}).get("created_utc")
                        if ts:
                            timestamps.append(int(ts))
            except Exception as exc:
                log.debug("activity_heatmap: comments fetch failed", error=str(exc))

        if not timestamps:
            return {"found": False, "username": username, "reason": "No public activity found"}

        # Build frequency distributions
        hour_dist: Counter[int] = Counter()
        dow_dist: Counter[int] = Counter()  # 0 = Monday, 6 = Sunday
        for ts in timestamps:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            hour_dist[dt.hour] += 1
            dow_dist[dt.weekday()] += 1

        # Find peak activity window
        peak_hour = max(hour_dist, key=lambda h: hour_dist[h]) if hour_dist else None
        peak_dow = max(dow_dist, key=lambda d: dow_dist[d]) if dow_dist else None

        # Estimate timezone: peak activity should fall in waking hours (8-22 local)
        # If peak UTC hour is H, assumed local peak hours ± 2h → roughly UTC offset
        estimated_utc_offset: int | None = None
        if peak_hour is not None:
            # Naive heuristic: assume peak activity is around 14:00 local
            estimated_utc_offset = 14 - peak_hour
            if estimated_utc_offset > 12:
                estimated_utc_offset -= 24
            elif estimated_utc_offset < -12:
                estimated_utc_offset += 24

        dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        return {
            "found": True,
            "username": username,
            "total_data_points": len(timestamps),
            "hour_distribution": dict(sorted(hour_dist.items())),
            "day_of_week_distribution": {dow_names[k]: v for k, v in sorted(dow_dist.items())},
            "peak_hour_utc": peak_hour,
            "peak_day_of_week": dow_names[peak_dow] if peak_dow is not None else None,
            "estimated_utc_offset": estimated_utc_offset,
            "estimated_timezone": f"UTC{'+' if (estimated_utc_offset or 0) >= 0 else ''}{estimated_utc_offset}" if estimated_utc_offset is not None else None,
            "analysis_note": "Based on Reddit public activity. Peak hours are in UTC.",
        }
