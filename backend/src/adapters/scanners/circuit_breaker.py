"""Circuit breaker pattern for external service calls — Redis-backed for multi-worker consistency."""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitBreaker:
    """Prevents cascading failures when external scanners are unavailable.

    State is stored in Redis so all Uvicorn/Celery workers share the same
    view of each scanner's health.  Falls back to in-process state when
    Redis is unavailable.

    After `failure_threshold` consecutive failures, the breaker opens for
    `recovery_timeout` seconds.  During that time all calls are rejected.
    After the timeout, one probe request is allowed (half-open).  If it
    succeeds the breaker closes; if it fails, it reopens.
    """

    _PREFIX = "circuit_breaker"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,
        name: str = "default",
        redis_client: "aioredis.Redis | None" = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._redis = redis_client
        # In-process fallback
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    # ── Redis helpers ─────────────────────────────────────────────────────────

    def _key(self, field: str) -> str:
        return f"{self._PREFIX}:{self.name}:{field}"

    async def _redis_get_int(self, field: str, default: int = 0) -> int:
        if self._redis is None:
            return default
        try:
            val = await self._redis.get(self._key(field))
            return int(val) if val is not None else default
        except Exception as exc:
            log.warning("circuit_breaker_redis_read_error", scanner=self.name, field=field, error=str(exc))
            return default

    async def _redis_set(self, field: str, value: str | int, ex: int | None = None) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(self._key(field), str(value), ex=ex)
        except Exception as exc:
            log.warning("circuit_breaker_redis_write_error", scanner=self.name, field=field, error=str(exc))

    # ── State resolution ──────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        """Synchronous state check against in-process fallback."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def async_state(self) -> CircuitState:
        """Async state check — queries Redis when available."""
        failure_count = await self._redis_get_int("failures")
        # last_failure_ts is stored as a wall-clock epoch (time.time()), so compare
        # against time.time() — NOT time.monotonic() which resets on process restart.
        last_failure = float(await self._redis_get_int("last_failure_ts", 0))

        if failure_count >= self.failure_threshold:
            if time.time() - last_failure >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    async def async_is_open(self) -> bool:
        return await self.async_state() == CircuitState.OPEN

    # ── State transitions ─────────────────────────────────────────────────────

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    async def async_record_success(self) -> None:
        self.record_success()
        await self._redis_set("failures", 0, ex=self.recovery_timeout * 2)
        log.debug("circuit_breaker_success", scanner=self.name)

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    async def async_record_failure(self, error_message: str = "") -> None:
        self.record_failure()
        ttl = self.recovery_timeout * 2
        ts = int(time.time())

        if self._redis is not None:
            try:
                # INCR is atomic — no read-modify-write race across workers
                new_count = await self._redis.incr(self._key("failures"))
                await self._redis.expire(self._key("failures"), ttl)
                await self._redis_set("last_failure_ts", ts, ex=ttl)
                if error_message:
                    await self._redis_set("last_error", error_message[:500], ex=ttl)
                await self._redis_set("last_error_at", ts, ex=ttl)
            except Exception:
                new_count = self._failure_count
        else:
            new_count = self._failure_count

        if new_count >= self.failure_threshold:
            log.warning("circuit_breaker_opened", scanner=self.name, failures=new_count)

    def reset(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = 0.0

    async def async_reset(self) -> None:
        self.reset()
        await self._redis_set("failures", 0, ex=self.recovery_timeout * 2)
