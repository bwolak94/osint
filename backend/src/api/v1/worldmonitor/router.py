"""WorldMonitor API router.

All endpoints are prefixed /worldmonitor/api (set in _ROUTER_REGISTRY).

Endpoints:
  GET /news               — paginated news feed with optional category filter
  GET /news/categories    — list of known categories with item counts
  GET /news/clusters      — stub (clustering impl in step 5)
  GET /health             — data freshness per Redis key
  GET /bootstrap          — batch hydration for the frontend cold start
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.worldmonitor.cache import CACHE_TIERS, get_list_json, make_etag
from src.worldmonitor.events_aggregator import KEY_EVENTS, KEY_EVENTS_META
from src.worldmonitor.social_scraper import KEY_POSTS, KEY_POSTS_META
from src.worldmonitor.rss_aggregator import (
    KEY_BY_CAT,
    KEY_LATEST,
    KEY_META,
    _load_feeds,
)

log = structlog.get_logger(__name__)

router = APIRouter()


# ── Dependency helpers ─────────────────────────────────────────────────────────

def _get_redis(request: Request) -> aioredis.Redis:
    redis: aioredis.Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Cache unavailable")
    return redis


CurrentUser = Annotated[User, Depends(get_current_user)]
RedisClient = Annotated[aioredis.Redis, Depends(_get_redis)]


def _etag_response(request: Request, data: Any, *, status: int = 200) -> JSONResponse:
    """Return JSON with ETag header; short-circuit 304 on cache hit."""
    etag = make_etag(data)
    if request.headers.get("if-none-match") == etag:
        return JSONResponse(status_code=304, content=None)
    return JSONResponse(
        status_code=status,
        content=data,
        headers={"ETag": etag, "Cache-Control": f"max-age={CACHE_TIERS['fast']}"},
    )


# ── /news ─────────────────────────────────────────────────────────────────────

_ALL_CATEGORIES = [
    "geopolitics", "military", "cyber", "economy",
    "disaster", "climate", "health", "energy", "tech",
]


@router.get("/news")
async def get_news(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
    category: str | None = Query(None, description="Filter by category slug"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> JSONResponse:
    """Return paginated news items from Redis cache.

    When no category is specified returns a balanced interleaved mix from all
    per-category lists so no single high-volume category (e.g. disaster)
    drowns out the others.
    """
    if category:
        all_items = await get_list_json(redis, KEY_BY_CAT.format(cat=category), 0, 499)
    else:
        # Fetch up to 50 items from each category then interleave round-robin
        per_cat: list[list[dict[str, Any]]] = await asyncio.gather(*[
            get_list_json(redis, KEY_BY_CAT.format(cat=cat), 0, 49)
            for cat in _ALL_CATEGORIES
        ])
        # Round-robin interleave so every category appears in the result
        all_items = []
        iterators = [iter(lst) for lst in per_cat]
        exhausted = [False] * len(iterators)
        while not all(exhausted):
            for i, it in enumerate(iterators):
                if exhausted[i]:
                    continue
                item = next(it, None)
                if item is None:
                    exhausted[i] = True
                else:
                    all_items.append(item)
        # Sort by published_at descending (newest first)
        all_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    total = len(all_items)
    start = (page - 1) * page_size
    page_items = all_items[start : start + page_size]

    return _etag_response(request, {
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "category": category,
    })


# ── /news/categories ──────────────────────────────────────────────────────────

@router.get("/news/categories")
async def get_categories(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
) -> JSONResponse:
    """Return category slugs with feed count and cached item count."""
    feeds = _load_feeds()
    feed_counts: dict[str, int] = {}
    for feed in feeds:
        feed_counts[feed["category"]] = feed_counts.get(feed["category"], 0) + 1

    # Batch Redis llen for each category
    cats = list(feed_counts.keys())
    pipe = redis.pipeline()
    for cat in cats:
        pipe.llen(KEY_BY_CAT.format(cat=cat))
    lengths = await pipe.execute()

    result = [
        {"category": cat, "feed_count": feed_counts[cat], "item_count": length}
        for cat, length in zip(cats, lengths, strict=True)
    ]
    return _etag_response(request, result)


# ── /news/clusters ────────────────────────────────────────────────────────────

@router.get("/news/clusters")
async def get_news_clusters(
    _user: CurrentUser,
) -> JSONResponse:
    """News clustering stub — full implementation arrives in step 5."""
    return JSONResponse(content={
        "clusters": [],
        "status": "not_implemented",
        "message": "Clustering (sentence-transformers + DBSCAN) implemented in step 5.",
    })


# ── /health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def get_health(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
) -> JSONResponse:
    """Report freshness and staleness of WorldMonitor Redis keys."""
    key_specs = [
        (KEY_LATEST, CACHE_TIERS["fast"]),
        (KEY_META, CACHE_TIERS["fast"]),
    ]

    pipe = redis.pipeline()
    for key, _ in key_specs:
        pipe.ttl(key)
    pipe.get(KEY_META)
    results = await pipe.execute()

    ttls: list[int] = results[:-1]
    meta_raw: str | None = results[-1]

    meta: dict[str, Any] = {}
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
        except json.JSONDecodeError:
            pass

    entries: list[dict[str, Any]] = []
    for (key, max_stale_s), ttl in zip(key_specs, ttls, strict=True):
        max_stale_min = max_stale_s / 60
        if ttl == -2:
            status, age_min = "EMPTY", None
        elif ttl == -1:
            status, age_min = "OK", 0.0
        else:
            age_s = max_stale_s - ttl
            age_min = round(age_s / 60, 1)
            status = "WARN" if ttl < max_stale_s * 0.1 else "OK"

        entries.append({
            "key": key,
            "fetched_at": meta.get("last_run"),
            "age_min": age_min,
            "max_stale_min": max_stale_min,
            "status": status,
        })

    overall_ok = all(e["status"] in ("OK", "WARN") for e in entries)
    return _etag_response(request, {
        "status": "OK" if overall_ok else "DEGRADED",
        "keys": entries,
        "last_aggregation": meta.get("last_run"),
        "items_fetched_last_run": meta.get("items_fetched"),
    })


# ── /posts ────────────────────────────────────────────────────────────────────

@router.get("/posts")
async def get_posts(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
    platform: str | None = Query(None, description="Filter by platform: x|truthsocial"),
    account_id: str | None = Query(None, description="Filter by account handle"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> JSONResponse:
    """Return paginated social posts from X/Twitter and Truth Social."""
    all_posts = await get_list_json(redis, KEY_POSTS, 0, 399)

    if platform:
        all_posts = [p for p in all_posts if p.get("platform") == platform]
    if account_id:
        all_posts = [p for p in all_posts if p.get("account_id", "").lower() == account_id.lower()]

    total = len(all_posts)
    start = (page - 1) * page_size
    page_posts = all_posts[start : start + page_size]

    meta_raw = await redis.get(KEY_POSTS_META)
    meta: dict[str, Any] = {}
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
        except json.JSONDecodeError:
            pass

    return _etag_response(request, {
        "items": page_posts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "last_updated": meta.get("last_run"),
        "account_counts": meta.get("account_counts", {}),
    })


# ── /map-events ───────────────────────────────────────────────────────────────

@router.get("/map-events")
async def get_map_events(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
    layer: str | None = Query(None, description="Filter by layer key"),
    severity: str | None = Query(None, description="Filter by severity: high|medium|low"),
    limit: int = Query(300, ge=1, le=500),
) -> JSONResponse:
    """Return live geospatial events from USGS, NASA EONET, GDACS, and Feodo Tracker."""
    all_events = await get_list_json(redis, KEY_EVENTS, 0, limit - 1)

    if layer:
        all_events = [e for e in all_events if e.get("layer") == layer]
    if severity:
        all_events = [e for e in all_events if e.get("severity") == severity]

    meta_raw = await redis.get(KEY_EVENTS_META)
    meta: dict[str, Any] = {}
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
        except json.JSONDecodeError:
            pass

    return _etag_response(request, {
        "events": all_events,
        "total": len(all_events),
        "last_updated": meta.get("last_run"),
        "source_counts": meta.get("source_counts", {}),
    })


# ── /stream ───────────────────────────────────────────────────────────────────

@router.get("/stream")
async def stream_news(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
) -> StreamingResponse:
    """SSE endpoint — pushes new news items as they arrive in Redis.

    Checks the Redis list every 20 s; emits `event: news` for each new item
    (newest-first order reversed so oldest arrives first).  Sends a heartbeat
    comment every cycle when no new items are found to keep the connection open
    through proxies.  The ``X-Accel-Buffering: no`` header disables nginx
    output-buffering so events reach the browser immediately.
    """

    async def _gen() -> AsyncGenerator[str, None]:
        last_id: str | None = None
        try:
            seed = await get_list_json(redis, KEY_LATEST, 0, 0)
            if seed:
                last_id = seed[0].get("id")
        except Exception:
            pass

        yield ": connected\n\n"

        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(20)
            if await request.is_disconnected():
                break

            try:
                items = await get_list_json(redis, KEY_LATEST, 0, 19)
                new_items: list[dict[str, Any]] = []
                for item in items:
                    if item.get("id") == last_id:
                        break
                    new_items.append(item)

                if new_items:
                    last_id = items[0].get("id") if items else last_id
                    for item in reversed(new_items):
                        yield f"event: news\ndata: {json.dumps(item)}\n\n"
                else:
                    yield f": heartbeat {int(time.time())}\n\n"

            except Exception as exc:
                log.warning("wm_sse_error", error=str(exc))
                yield ": error\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── /bootstrap ────────────────────────────────────────────────────────────────

@router.get("/bootstrap")
async def bootstrap(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
) -> JSONResponse:
    """Single-request cold-start hydration for the frontend dashboard."""
    news_coro = get_list_json(redis, KEY_LATEST, 0, 49)
    meta_coro = redis.get(KEY_META)
    total_coro = redis.llen(KEY_LATEST)
    events_coro = get_list_json(redis, KEY_EVENTS, 0, 299)
    events_meta_coro = redis.get(KEY_EVENTS_META)

    news_items, meta_raw, total, events, events_meta_raw = await asyncio.gather(
        news_coro, meta_coro, total_coro, events_coro, events_meta_coro,
    )

    meta: dict[str, Any] = {}
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
        except json.JSONDecodeError:
            pass

    events_meta: dict[str, Any] = {}
    if events_meta_raw:
        try:
            events_meta = json.loads(events_meta_raw)
        except json.JSONDecodeError:
            pass

    feeds = _load_feeds()
    categories = sorted({f["category"] for f in feeds})

    return _etag_response(request, {
        "news": {"items": news_items, "total_cached": total},
        "events": {"items": events, "total": len(events), "last_updated": events_meta.get("last_run")},
        "categories": categories,
        "meta": meta,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
