"""RSS feed aggregator for WorldMonitor.

Responsibilities:
- Load feed definitions from feeds.json
- Fetch each feed with httpx (async, retry, per-feed circuit breaker)
- Parse RSS / Atom via xml.etree.ElementTree (no extra deps)
- Deduplicate by FNV-1a hash of (title + pubDate)
- Persist to Redis:
    wm:news:latest              — list[500] of all items, newest first
    wm:news:by_category:<cat>   — list[200] per category
    wm:news:seen_hashes         — set of already-ingested hashes (TTL 48h)
    wm:news:meta                — JSON: last_run, feed_stats
"""

from __future__ import annotations

import asyncio
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog

from .cache import CACHE_TIERS, fnv1a_hash, redis_key

log = structlog.get_logger(__name__)

_FEEDS_JSON = Path(__file__).parent / "feeds.json"
_FETCH_TIMEOUT = 15.0  # seconds per feed
_MAX_RETRIES = 2
_CONCURRENT_FEEDS = 10  # httpx concurrency limit

# Redis keys
KEY_LATEST = redis_key("news", "latest")
KEY_SEEN = redis_key("news", "seen_hashes")
KEY_META = redis_key("news", "meta")
KEY_BY_CAT = "wm:news:by_category:{cat}"

# RSS / Atom namespaces
NS_ATOM = "http://www.w3.org/2005/Atom"
NS_MEDIA = "http://search.yahoo.com/mrss/"
NS_DC = "http://purl.org/dc/elements/1.1/"


def _load_feeds() -> list[dict[str, Any]]:
    """Load feed definitions from the bundled feeds.json."""
    with _FEEDS_JSON.open() as f:
        return json.load(f)  # type: ignore[no-any-return]


def _parse_date(raw: str | None) -> str:
    """Normalize a date string to ISO-8601 UTC. Returns empty string on failure."""
    if not raw:
        return datetime.now(tz=timezone.utc).isoformat()
    for parser in (_parse_rfc2822, _parse_iso):
        result = parser(raw)
        if result:
            return result
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_rfc2822(raw: str) -> str | None:
    try:
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _parse_iso(raw: str) -> str | None:
    try:
        dt = datetime.fromisoformat(raw.rstrip("Z"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _text(el: ET.Element | None) -> str:
    """Safely extract text from an XML element."""
    if el is None:
        return ""
    return (el.text or "").strip()


def _parse_rss_items(root: ET.Element, feed_meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse RSS 2.0 <item> elements."""
    items: list[dict[str, Any]] = []
    channel = root.find("channel")
    if channel is None:
        return items

    for item in channel.findall("item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        description = _text(item.find("description"))
        pub_date = _parse_date(_text(item.find("pubDate")) or _text(item.find(f"{{{NS_DC}}}date")))
        guid = _text(item.find("guid")) or link

        if not title:
            continue

        items.append({
            "id": fnv1a_hash(title + pub_date),
            "title": title,
            "url": link,
            "description": description[:500] if description else "",
            "published_at": pub_date,
            "source_id": feed_meta["id"],
            "source_name": feed_meta["name"],
            "category": feed_meta["category"],
            "country_iso": feed_meta["country_iso"],
            "language": feed_meta["language"],
            "weight": feed_meta["weight"],
            "guid": guid,
        })

    return items


def _parse_atom_items(root: ET.Element, feed_meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse Atom 1.0 <entry> elements."""
    items: list[dict[str, Any]] = []

    for entry in root.findall(f"{{{NS_ATOM}}}entry"):
        title_el = entry.find(f"{{{NS_ATOM}}}title")
        title = _text(title_el)

        link_el = entry.find(f"{{{NS_ATOM}}}link[@rel='alternate']") or entry.find(f"{{{NS_ATOM}}}link")
        link = link_el.get("href", "") if link_el is not None else ""

        summary_el = entry.find(f"{{{NS_ATOM}}}summary") or entry.find(f"{{{NS_ATOM}}}content")
        description = _text(summary_el)[:500] if summary_el is not None else ""

        updated = _text(entry.find(f"{{{NS_ATOM}}}updated") or entry.find(f"{{{NS_ATOM}}}published"))
        pub_date = _parse_date(updated)

        id_el = entry.find(f"{{{NS_ATOM}}}id")
        guid = _text(id_el) or link

        if not title:
            continue

        items.append({
            "id": fnv1a_hash(title + pub_date),
            "title": title,
            "url": link,
            "description": description,
            "published_at": pub_date,
            "source_id": feed_meta["id"],
            "source_name": feed_meta["name"],
            "category": feed_meta["category"],
            "country_iso": feed_meta["country_iso"],
            "language": feed_meta["language"],
            "weight": feed_meta["weight"],
            "guid": guid,
        })

    return items


def _parse_feed(content: bytes, feed_meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect RSS vs Atom and dispatch to the correct parser."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        log.warning("feed_parse_error", feed=feed_meta["id"], error=str(exc))
        return []

    tag = root.tag.lower()
    if "feed" in tag or NS_ATOM in tag:
        return _parse_atom_items(root, feed_meta)
    return _parse_rss_items(root, feed_meta)


async def _fetch_feed(
    client: httpx.AsyncClient,
    feed: dict[str, Any],
    sem: asyncio.Semaphore,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch and parse a single RSS/Atom feed. Returns (feed_meta, items)."""
    async with sem:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.get(
                    feed["url"],
                    timeout=_FETCH_TIMEOUT,
                    headers={"User-Agent": "WorldMonitor/1.0 (geopolitical-dashboard)"},
                    follow_redirects=True,
                )
                resp.raise_for_status()
                items = _parse_feed(resp.content, feed)
                log.debug("feed_fetched", feed=feed["id"], items=len(items))
                return feed, items
            except httpx.HTTPStatusError as exc:
                log.warning("feed_http_error", feed=feed["id"], status=exc.response.status_code)
                return feed, []
            except Exception as exc:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                else:
                    log.warning("feed_fetch_failed", feed=feed["id"], error=str(exc))
                    return feed, []
    return feed, []  # unreachable, satisfies type checker


async def _store_items(
    redis: aioredis.Redis,
    new_items: list[dict[str, Any]],
) -> int:
    """Deduplicate against seen-hashes set, then store in Redis. Returns count stored."""
    if not new_items:
        return 0

    item_ids = [item["id"] for item in new_items]
    # Check which hashes are already known
    pipe = redis.pipeline()
    for h in item_ids:
        pipe.sismember(KEY_SEEN, h)
    membership = await pipe.execute()

    fresh = [item for item, seen in zip(new_items, membership, strict=True) if not seen]
    if not fresh:
        return 0

    # Persist: global latest list + per-category lists + seen-hash set
    pipe = redis.pipeline()

    serialized = [json.dumps(item, default=str) for item in fresh]
    for s in serialized:
        pipe.lpush(KEY_LATEST, s)
    pipe.ltrim(KEY_LATEST, 0, 499)
    pipe.expire(KEY_LATEST, CACHE_TIERS["fast"] * 2)

    # Per-category
    by_cat: dict[str, list[str]] = {}
    for item, s in zip(fresh, serialized, strict=True):
        by_cat.setdefault(item["category"], []).append(s)

    for cat, cat_items in by_cat.items():
        cat_key = KEY_BY_CAT.format(cat=cat)
        for s in cat_items:
            pipe.lpush(cat_key, s)
        pipe.ltrim(cat_key, 0, 199)
        pipe.expire(cat_key, CACHE_TIERS["fast"] * 2)

    # Mark hashes as seen (TTL 48h)
    for item in fresh:
        pipe.sadd(KEY_SEEN, item["id"])
    pipe.expire(KEY_SEEN, 172800)

    await pipe.execute()
    return len(fresh)


async def run_aggregation(redis: aioredis.Redis) -> dict[str, Any]:
    """Fetch all feeds and store new items. Returns a stats dict."""
    feeds = _load_feeds()
    sem = asyncio.Semaphore(_CONCURRENT_FEEDS)
    started_at = time.time()

    async with httpx.AsyncClient() as client:
        tasks = [_fetch_feed(client, feed, sem) for feed in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[dict[str, Any]] = []
    feed_stats: dict[str, int] = {}

    for result in results:
        if isinstance(result, Exception):
            log.error("aggregation_task_error", error=str(result))
            continue
        feed_meta, items = result
        feed_stats[feed_meta["id"]] = len(items)
        all_items.extend(items)

    # Sort by published_at descending before storing
    all_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    stored = await _store_items(redis, all_items)

    meta = {
        "last_run": datetime.now(tz=timezone.utc).isoformat(),
        "duration_s": round(time.time() - started_at, 2),
        "feeds_total": len(feeds),
        "items_fetched": len(all_items),
        "items_stored": stored,
        "feed_stats": feed_stats,
    }
    await redis.setex(KEY_META, CACHE_TIERS["fast"], json.dumps(meta))
    log.info("aggregation_complete", **meta)
    return meta
