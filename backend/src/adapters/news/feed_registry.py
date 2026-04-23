"""News feed registry — stores configurable RSS feed sources.

Sources are persisted in Redis (simple key-value, TTL=forever) so they
survive restarts and can be managed via the API without a DB migration.
"""
from __future__ import annotations

import json
from typing import Any

from src.adapters.news.rss_scraper import DEFAULT_FEED_URLS

_REGISTRY_KEY = "news:feeds:registry"
_TTL = 0  # no expiry


async def get_feeds(redis: Any) -> list[dict[str, Any]]:
    """Return all registered feeds. Initialises from defaults on first call."""
    raw = await redis.get(_REGISTRY_KEY)
    if raw is None:
        feeds = [
            {"url": url, "name": url.split("/")[2], "enabled": True, "added_at": ""}
            for url in DEFAULT_FEED_URLS
        ]
        await redis.set(_REGISTRY_KEY, json.dumps(feeds))
        return feeds
    return json.loads(raw)


async def add_feed(redis: Any, url: str, name: str) -> dict[str, Any]:
    feeds = await get_feeds(redis)
    from datetime import datetime, timezone
    new_feed = {"url": url, "name": name, "enabled": True, "added_at": datetime.now(timezone.utc).isoformat()}
    feeds.append(new_feed)
    await redis.set(_REGISTRY_KEY, json.dumps(feeds))
    return new_feed


async def remove_feed(redis: Any, url: str) -> bool:
    feeds = await get_feeds(redis)
    new_feeds = [f for f in feeds if f["url"] != url]
    if len(new_feeds) == len(feeds):
        return False
    await redis.set(_REGISTRY_KEY, json.dumps(new_feeds))
    return True


async def toggle_feed(redis: Any, url: str, enabled: bool) -> bool:
    feeds = await get_feeds(redis)
    for feed in feeds:
        if feed["url"] == url:
            feed["enabled"] = enabled
            await redis.set(_REGISTRY_KEY, json.dumps(feeds))
            return True
    return False
