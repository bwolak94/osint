"""Unit tests for circuit breaker Redis fallback and DAG pipeline cycle detection."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# CircuitBreaker — Redis unavailable fallback
# ---------------------------------------------------------------------------

class TestCircuitBreakerRedisFallback:

    async def test_falls_back_to_in_process_on_redis_connection_error(self):
        """When Redis raises ConnectionError, the CB must not crash and must
        still track failures in-process."""
        from src.adapters.scanners.circuit_breaker import CircuitBreaker

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
        mock_redis.expire = AsyncMock(side_effect=ConnectionError())
        mock_redis.set = AsyncMock(side_effect=ConnectionError())
        mock_redis.get = AsyncMock(side_effect=ConnectionError())

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name="test", redis_client=mock_redis)

        # Should not raise even though Redis is down
        await cb.async_record_failure("simulated error")
        await cb.async_record_failure("simulated error")
        await cb.async_record_failure("simulated error")

        # In-process counter should be at 3
        assert cb._failure_count == 3

    async def test_async_record_success_resets_in_process_state(self):
        from src.adapters.scanners.circuit_breaker import CircuitBreaker, CircuitState

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"0")

        cb = CircuitBreaker(failure_threshold=3, name="test2", redis_client=mock_redis)
        cb._failure_count = 2
        await cb.async_record_success()
        assert cb._failure_count == 0
        assert cb._state == CircuitState.CLOSED

    async def test_incr_is_used_for_atomic_failure_counting(self):
        """async_record_failure must call INCR (not GET+SET) for atomicity."""
        from src.adapters.scanners.circuit_breaker import CircuitBreaker

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        mock_redis.set = AsyncMock()

        cb = CircuitBreaker(failure_threshold=5, name="test3", redis_client=mock_redis)
        await cb.async_record_failure("test error")

        mock_redis.incr.assert_called_once()
        call_args = mock_redis.incr.call_args[0][0]
        assert "failures" in call_args


# ---------------------------------------------------------------------------
# DAG pipeline — cycle detection
# ---------------------------------------------------------------------------

class TestDagPipelineCycleDetection:

    def test_raises_on_circular_dependency(self):
        """topological_sort must raise ValueError when scanners form a cycle."""
        from src.adapters.scanners.dag_pipeline import topological_sort, SCANNER_DEPENDENCIES

        # Temporarily inject a cycle: A -> B -> A
        original = dict(SCANNER_DEPENDENCIES)
        SCANNER_DEPENDENCIES["scanner_a"] = {"scanner_b"}
        SCANNER_DEPENDENCIES["scanner_b"] = {"scanner_a"}

        try:
            with pytest.raises(ValueError, match="Circular dependency"):
                topological_sort(["scanner_a", "scanner_b"])
        finally:
            # Clean up injected cycle
            SCANNER_DEPENDENCIES.pop("scanner_a", None)
            SCANNER_DEPENDENCIES.pop("scanner_b", None)

    def test_no_dependencies_returns_single_phase(self):
        """Scanners with no shared dependencies should all be in one phase."""
        from src.adapters.scanners.dag_pipeline import topological_sort

        phases = topological_sort(["shodan_scanner", "hibp_scanner", "virustotal_scanner"])
        assert len(phases) == 1
        assert set(phases[0]) == {"shodan_scanner", "hibp_scanner", "virustotal_scanner"}

    def test_dependency_ordering(self):
        """httpx_probe_scanner depends on subdomain_scanner — must be in a later phase."""
        from src.adapters.scanners.dag_pipeline import topological_sort

        phases = topological_sort(["subdomain_scanner", "httpx_probe_scanner"])
        phase_0 = set(phases[0])
        phase_1 = set(phases[1]) if len(phases) > 1 else set()

        assert "subdomain_scanner" in phase_0
        assert "httpx_probe_scanner" in phase_1
