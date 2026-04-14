"""Circuit breaker pattern for external service calls."""

import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Prevents cascading failures when external scanners are unavailable.

    After `failure_threshold` consecutive failures, the breaker opens for
    `recovery_timeout` seconds. During that time all calls are rejected.
    After the timeout, one probe request is allowed (half-open). If it
    succeeds the breaker closes; if it fails, it reopens.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,
        name: str = "default",
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._success_count = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    def record_success(self) -> None:
        self._failure_count = 0
        self._success_count += 1
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        self._failure_count = 0
        self._success_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = 0.0
