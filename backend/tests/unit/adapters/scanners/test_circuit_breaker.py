import time
import pytest
from src.adapters.scanners.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.is_closed is True

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open is True

    def test_success_resets_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_closed is True  # reset after success

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)  # instant recovery
        cb.record_failure()
        # With recovery_timeout=0 the breaker transitions to HALF_OPEN on the
        # very next state check because the timeout has already elapsed.
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.is_closed is True

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.is_open is True
        cb.reset()
        assert cb.is_closed is True
