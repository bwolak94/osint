"""Redis-backed cache for scan results."""

import json
from typing import Any

from redis.asyncio import Redis


class RedisCache:
    """Caches scan results in Redis with configurable TTL."""

    PREFIX = "scan_cache:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis.get(f"{self.PREFIX}{key}")
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: dict[str, Any], ttl: int = 86400) -> None:
        await self._redis.setex(f"{self.PREFIX}{key}", ttl, json.dumps(value, default=str))

    async def delete(self, key: str) -> None:
        await self._redis.delete(f"{self.PREFIX}{key}")

    async def exists(self, key: str) -> bool:
        return await self._redis.exists(f"{self.PREFIX}{key}") > 0
