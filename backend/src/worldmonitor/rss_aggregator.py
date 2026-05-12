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

_IMG_RE = __import__("re").compile(r'<img[^>]+src=["\']([^"\']+)["\']', __import__("re").IGNORECASE)


def _extract_image(item: ET.Element, description: str) -> str:
    """Extract best available image URL from an RSS/Atom item."""
    # media:content
    mc = item.find(f"{{{NS_MEDIA}}}content")
    if mc is not None:
        url = mc.get("url", "")
        mime = mc.get("type", "")
        if url and (not mime or mime.startswith("image/")):
            return url
    # media:thumbnail
    mt = item.find(f"{{{NS_MEDIA}}}thumbnail")
    if mt is not None:
        url = mt.get("url", "")
        if url:
            return url
    # enclosure
    enc = item.find("enclosure")
    if enc is not None:
        url = enc.get("url", "")
        mime = enc.get("type", "")
        if url and mime.startswith("image/"):
            return url
    # first <img> in description HTML
    m = _IMG_RE.search(description or "")
    if m:
        return m.group(1)
    return ""


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
        image_url = _extract_image(item, description)

        if not title:
            continue

        entry: dict[str, Any] = {
            "id": fnv1a_hash(title + pub_date),
            "title": title,
            "url": link,
            "description": description[:800] if description else "",
            "published_at": pub_date,
            "source_id": feed_meta["id"],
            "source_name": feed_meta["name"],
            "category": feed_meta["category"],
            "country_iso": feed_meta["country_iso"],
            "language": feed_meta["language"],
            "weight": feed_meta["weight"],
            "guid": guid,
        }
        if image_url:
            entry["image_url"] = image_url
        items.append(entry)

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
        description = _text(summary_el)[:800] if summary_el is not None else ""

        updated = _text(entry.find(f"{{{NS_ATOM}}}updated") or entry.find(f"{{{NS_ATOM}}}published"))
        pub_date = _parse_date(updated)

        id_el = entry.find(f"{{{NS_ATOM}}}id")
        guid = _text(id_el) or link
        image_url = _extract_image(entry, description)

        if not title:
            continue

        atom_entry: dict[str, Any] = {
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
        }
        if image_url:
            atom_entry["image_url"] = image_url
        items.append(atom_entry)

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
    """Store items to Redis.

    Strategy:
    - Global ``wm:news:latest``: deduplicated by seen-hash, newest-first, max 500, TTL 48h.
    - Per-category lists: rebuilt completely from the current run's full batch each time
      (no dedup — avoids empty lists after TTL expiry), max 200, TTL 48h.
    """
    if not new_items:
        return 0

    # ── 1. Determine which items are new to the global latest list ──────────
    item_ids = [item["id"] for item in new_items]
    pipe = redis.pipeline()
    for h in item_ids:
        pipe.sismember(KEY_SEEN, h)
    membership = await pipe.execute()

    fresh = [item for item, seen in zip(new_items, membership, strict=True) if not seen]

    big_pipe = redis.pipeline()

    # ── 2. Prepend fresh items to global latest list ─────────────────────────
    if fresh:
        for item in fresh:
            big_pipe.lpush(KEY_LATEST, json.dumps(item, default=str))
        big_pipe.ltrim(KEY_LATEST, 0, 499)
        big_pipe.expire(KEY_LATEST, 172800)  # 48 h

        for item in fresh:
            big_pipe.sadd(KEY_SEEN, item["id"])
        big_pipe.expire(KEY_SEEN, 172800)  # 48 h

    # ── 3. Rebuild every category list from the full current-run batch ───────
    # This runs regardless of dedup state so lists never go stale/empty.
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in new_items:
        by_cat.setdefault(item["category"], []).append(item)

    for cat, cat_items in by_cat.items():
        cat_key = KEY_BY_CAT.format(cat=cat)
        big_pipe.delete(cat_key)
        for item in cat_items[:200]:
            big_pipe.rpush(cat_key, json.dumps(item, default=str))
        big_pipe.expire(cat_key, 172800)  # 48 h

    await big_pipe.execute()
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
