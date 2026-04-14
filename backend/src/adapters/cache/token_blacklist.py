from redis.asyncio import Redis


class RedisTokenBlacklist:
    """Redis-based token blacklist for immediate JWT invalidation."""

    PREFIX = "token_blacklist:"

    def __init__(self, redis: Redis):
        self._redis = redis

    async def blacklist(self, token: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        key = f"{self.PREFIX}{token}"
        await self._redis.setex(key, ttl_seconds, "1")

    async def is_blacklisted(self, token: str) -> bool:
        key = f"{self.PREFIX}{token}"
        return await self._redis.exists(key) > 0
