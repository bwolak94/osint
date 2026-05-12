"""Redis cache helpers for WorldMonitor.

Cache tiers:
  fast   = 300s   (news items, market tickers)
  medium = 600s   (clustered news)
  slow   = 1800s  (CII scores)
  static = 7200s  (reference data, country metadata)
  daily  = 86400s (baseline statistics)

ETag uses FNV-1a hash for fast, deterministic fingerprinting.
Concurrent cache-miss coalescing via Redis NX lock.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger(__name__)

CACHE_TIERS: dict[str, int] = {
    "fast": 300,
    "medium": 600,
    "slow": 1800,
    "static": 7200,
    "daily": 86400,
}

# Redis key namespace
NS = "wm"


def redis_key(*parts: str) -> str:
    """Build a namespaced Redis key."""
    return f"{NS}:" + ":".join(parts)


def fnv1a_hash(data: str) -> str:
    """FNV-1a 32-bit hash — fast, deterministic, suitable for ETags."""
    h = 2166136261
    for byte in data.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return format(h, "08x")


def make_etag(data: Any) -> str:
    """Generate an ETag string from any JSON-serializable value."""
    return f'"{fnv1a_hash(json.dumps(data, sort_keys=True, default=str))}"'


async def cached_fetch_json(
    redis: aioredis.Redis,
    key: str,
    fetch_fn: Callable[[], Awaitable[Any]],
    ttl: int = CACHE_TIERS["medium"],
    lock_timeout: int = 15,
) -> Any:
    """Return cached JSON value, fetching and caching on miss.

    Concurrent misses are coalesced: the first coroutine acquires a Redis NX
    lock, fetches, and writes; all others spin-wait up to *lock_timeout* seconds
    then return the freshly populated value.
    """
    cached = await redis.get(key)
    if cached is not None:
        return json.loads(cached)

    lock_key = redis_key("lock", key)
    acquired = await redis.set(lock_key, "1", nx=True, ex=lock_timeout)

    if not acquired:
        # Another coroutine is fetching — wait for it
        deadline = asyncio.get_event_loop().time() + lock_timeout
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.5)
            cached = await redis.get(key)
            if cached is not None:
                return json.loads(cached)
        log.warning("cache_miss_coalesce_timeout", key=key)
        # Fall through and fetch ourselves as a safety net
        data = await fetch_fn()
        return data

    try:
        data = await fetch_fn()
        serialized = json.dumps(data, default=str)
        await redis.setex(key, ttl, serialized)
        return data
    except Exception as exc:
        log.error("cache_fetch_error", key=key, error=str(exc))
        raise
    finally:
        await redis.delete(lock_key)


async def get_list_json(
    redis: aioredis.Redis,
    key: str,
    start: int = 0,
    stop: int = -1,
) -> list[Any]:
    """Retrieve a Redis list as a list of parsed JSON objects."""
    raw_items = await redis.lrange(key, start, stop)
    result: list[Any] = []
    for raw in raw_items:
        try:
            result.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return result


async def push_list_json(
    redis: aioredis.Redis,
    key: str,
    items: list[Any],
    max_len: int = 500,
    ttl: int = CACHE_TIERS["fast"],
) -> None:
    """Prepend JSON items to a Redis list, trimming to *max_len*."""
    if not items:
        return
    pipe = redis.pipeline()
    for item in items:
        pipe.lpush(key, json.dumps(item, default=str))
    pipe.ltrim(key, 0, max_len - 1)
    pipe.expire(key, ttl)
    await pipe.execute()
