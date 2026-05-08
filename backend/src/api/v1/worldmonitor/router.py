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
from typing import Annotated, Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.worldmonitor.cache import CACHE_TIERS, get_list_json, make_etag
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

@router.get("/news")
async def get_news(
    request: Request,
    redis: RedisClient,
    _user: CurrentUser,
    category: str | None = Query(None, description="Filter by category slug"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> JSONResponse:
    """Return paginated news items from Redis cache."""
    if category:
        key = KEY_BY_CAT.format(cat=category)
        max_items = 200
    else:
        key = KEY_LATEST
        max_items = 500

    all_items = await get_list_json(redis, key, 0, max_items - 1)

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

    news_items, meta_raw, total = await asyncio.gather(news_coro, meta_coro, total_coro)

    meta: dict[str, Any] = {}
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
        except json.JSONDecodeError:
            pass

    feeds = _load_feeds()
    categories = sorted({f["category"] for f in feeds})

    return _etag_response(request, {
        "news": {"items": news_items, "total_cached": total},
        "categories": categories,
        "meta": meta,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
