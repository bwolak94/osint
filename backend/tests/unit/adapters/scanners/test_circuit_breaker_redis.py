"""Tests for the Redis-backed async methods of CircuitBreaker."""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.scanners.circuit_breaker import CircuitBreaker, CircuitState


class FakeRedis:
    """Minimal in-memory Redis mock for circuit breaker tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}  # key → (value, expires_at)

    def _is_alive(self, key: str) -> bool:
        if key not in self._store:
            return False
        _, expires_at = self._store[key]
        if expires_at is not None and time.time() > expires_at:
            del self._store[key]
            return False
        return True

    async def get(self, key: str) -> bytes | None:
        if not self._is_alive(key):
            return None
        return self._store[key][0].encode()

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        expires_at = time.time() + ex if ex is not None else None
        self._store[key] = (str(value), expires_at)

    async def incr(self, key: str) -> int:
        if not self._is_alive(key):
            self._store[key] = ("0", None)
        current = int(self._store[key][0])
        new_val = current + 1
        self._store[key] = (str(new_val), self._store[key][1])
        return new_val

    async def expire(self, key: str, seconds: int) -> None:
        if key in self._store:
            val, _ = self._store[key]
            self._store[key] = (val, time.time() + seconds)


class TestCircuitBreakerRedis:
    async def test_async_state_closed_when_no_redis_data(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=3, name="test_closed", redis_client=redis)
        state = await cb.async_state()
        assert state == CircuitState.CLOSED

    async def test_async_record_failure_increments_redis(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=3, name="test_incr", redis_client=redis)

        await cb.async_record_failure("connection error")
        await cb.async_record_failure("connection error")

        failures = await redis.get("circuit_breaker:test_incr:failures")
        assert failures is not None
        assert int(failures) == 2

    async def test_async_state_open_after_threshold_failures(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=3, name="test_open", redis_client=redis)

        for _ in range(3):
            await cb.async_record_failure("error")

        state = await cb.async_state()
        assert state == CircuitState.OPEN

    async def test_async_state_half_open_after_recovery_timeout(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0, name="test_halfopen", redis_client=redis)

        await cb.async_record_failure("error")
        # With recovery_timeout=0, last_failure_ts is in the past
        state = await cb.async_state()
        assert state == CircuitState.HALF_OPEN

    async def test_async_record_success_resets_redis_count(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=3, name="test_reset", redis_client=redis)

        await cb.async_record_failure("error")
        await cb.async_record_failure("error")
        await cb.async_record_success()

        # After success, failure count in Redis should be 0
        failures = await redis.get("circuit_breaker:test_reset:failures")
        assert failures is None or int(failures) == 0

    async def test_async_reset_clears_redis(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=1, name="test_async_reset", redis_client=redis)

        await cb.async_record_failure("error")
        assert await cb.async_is_open() is True

        await cb.async_reset()
        state = await cb.async_state()
        assert state == CircuitState.CLOSED

    async def test_redis_unavailable_falls_back_to_in_process(self) -> None:
        """When Redis raises, the in-process state is used — no exception propagates."""
        broken_redis = MagicMock()
        broken_redis.incr = AsyncMock(side_effect=ConnectionError("Redis down"))
        broken_redis.expire = AsyncMock(side_effect=ConnectionError("Redis down"))
        broken_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        broken_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        cb = CircuitBreaker(failure_threshold=2, name="test_fallback", redis_client=broken_redis)

        # Should not raise — falls back to in-process
        await cb.async_record_failure("error")
        await cb.async_record_failure("error")

        # In-process state should be OPEN
        assert cb.is_open is True

    async def test_multiple_workers_share_state_via_redis(self) -> None:
        """Two CircuitBreaker instances sharing the same Redis namespace converge."""
        redis = FakeRedis()
        cb1 = CircuitBreaker(failure_threshold=3, name="shared", redis_client=redis)
        cb2 = CircuitBreaker(failure_threshold=3, name="shared", redis_client=redis)

        # Worker 1 records failures
        await cb1.async_record_failure("error")
        await cb1.async_record_failure("error")
        await cb1.async_record_failure("error")

        # Worker 2 should see the same state via Redis
        state = await cb2.async_state()
        assert state == CircuitState.OPEN

    async def test_error_message_stored_in_redis(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=5, name="test_errmsg", redis_client=redis)

        await cb.async_record_failure("Scanner returned 503")

        last_error = await redis.get("circuit_breaker:test_errmsg:last_error")
        assert last_error is not None
        assert b"503" in last_error

    async def test_async_is_open_returns_bool(self) -> None:
        redis = FakeRedis()
        cb = CircuitBreaker(failure_threshold=2, name="test_is_open", redis_client=redis)

        assert await cb.async_is_open() is False

        await cb.async_record_failure("err")
        await cb.async_record_failure("err")

        assert await cb.async_is_open() is True
