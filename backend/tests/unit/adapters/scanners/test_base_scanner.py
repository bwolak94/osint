import pytest
from typing import Any
from uuid import uuid4

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.circuit_breaker import CircuitBreaker
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType, ScanStatus


class FakeCache:
    """In-memory cache for testing."""
    def __init__(self):
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> dict | None:
        return self._store.get(key)

    async def set(self, key: str, value: dict, ttl: int = 86400) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store


class SuccessScanner(BaseOsintScanner):
    scanner_name = "test_success"
    supported_input_types = frozenset({ScanInputType.EMAIL})
    call_count = 0

    async def _do_scan(self, input_value, input_type):
        self.call_count += 1
        return {"found": True, "extracted_identifiers": ["service:twitter"]}


class FailingScanner(BaseOsintScanner):
    scanner_name = "test_failing"
    supported_input_types = frozenset({ScanInputType.EMAIL})

    async def _do_scan(self, input_value, input_type):
        raise RuntimeError("Connection refused")


class RateLimitedScanner(BaseOsintScanner):
    scanner_name = "test_ratelimited"
    supported_input_types = frozenset({ScanInputType.EMAIL})

    async def _do_scan(self, input_value, input_type):
        raise RateLimitError("429 Too Many Requests")


class TestBaseScanner:
    async def test_successful_scan_returns_result(self):
        scanner = SuccessScanner()
        result = await scanner.scan("test@example.com", ScanInputType.EMAIL)
        assert result.status == ScanStatus.SUCCESS
        assert result.scanner_name == "test_success"
        assert result.duration_ms >= 0

    async def test_failed_scan_returns_failed_status(self):
        scanner = FailingScanner()
        result = await scanner.scan("test@example.com", ScanInputType.EMAIL)
        assert result.status == ScanStatus.FAILED
        assert result.error_message is not None
        assert "Connection refused" in result.error_message

    async def test_rate_limited_scan_returns_rate_limited(self):
        scanner = RateLimitedScanner()
        result = await scanner.scan("test@example.com", ScanInputType.EMAIL)
        assert result.status == ScanStatus.RATE_LIMITED

    async def test_cached_result_not_rescanned(self):
        cache = FakeCache()
        scanner = SuccessScanner(cache=cache)
        scanner.call_count = 0

        # First call -- hits the scanner
        r1 = await scanner.scan("test@example.com", ScanInputType.EMAIL)
        assert r1.status == ScanStatus.SUCCESS
        assert scanner.call_count == 1

        # Second call -- should hit cache
        r2 = await scanner.scan("test@example.com", ScanInputType.EMAIL)
        assert r2.status == ScanStatus.SUCCESS
        assert scanner.call_count == 1  # NOT incremented

    async def test_circuit_breaker_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=2, name="test")
        scanner = FailingScanner(circuit_breaker=cb)

        await scanner.scan("a@b.com", ScanInputType.EMAIL)
        await scanner.scan("a@b.com", ScanInputType.EMAIL)

        # Circuit breaker should be open now
        result = await scanner.scan("a@b.com", ScanInputType.EMAIL)
        assert result.status == ScanStatus.FAILED
        assert "circuit breaker" in result.error_message.lower()

    async def test_supports_input_type(self):
        scanner = SuccessScanner()
        assert scanner.supports(ScanInputType.EMAIL) is True
        assert scanner.supports(ScanInputType.USERNAME) is False

    async def test_extracted_identifiers_from_raw_data(self):
        scanner = SuccessScanner()
        result = await scanner.scan("test@example.com", ScanInputType.EMAIL)
        assert "service:twitter" in result.extracted_identifiers

    async def test_investigation_id_propagated(self):
        scanner = SuccessScanner()
        inv_id = uuid4()
        result = await scanner.scan("test@example.com", ScanInputType.EMAIL, investigation_id=inv_id)
        assert result.investigation_id == inv_id
