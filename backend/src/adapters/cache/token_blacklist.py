from redis.asyncio import Redis


class RedisTokenBlacklist:
    """Redis-based token blacklist for immediate JWT invalidation.

    Uses the JWT ID (``jti`` claim) as the Redis key instead of the full token
    string. A jti is 32 hex characters (~32 bytes) versus a JWT which can
    easily exceed 500 bytes, saving roughly 90 % of Redis memory per entry.
    """

    PREFIX = "token_blacklist:"

    def __init__(self, redis: Redis):
        self._redis = redis

    async def blacklist(self, jti: str, ttl_seconds: int) -> None:
        """Add *jti* to the blacklist with the given TTL.

        No-ops when ttl_seconds <= 0 (token already expired — nothing to revoke).
        """
        if ttl_seconds <= 0 or not jti:
            return
        key = f"{self.PREFIX}{jti}"
        await self._redis.setex(key, ttl_seconds, "1")

    async def is_blacklisted(self, jti: str) -> bool:
        """Return ``True`` when *jti* is present in the blacklist."""
        if not jti:
            return False
        key = f"{self.PREFIX}{jti}"
        return await self._redis.exists(key) > 0
