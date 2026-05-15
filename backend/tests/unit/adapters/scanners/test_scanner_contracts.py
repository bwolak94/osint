"""Scanner contract tests — verify every registered scanner meets the base contract.

These tests run against the real scanner registry (no external network calls)
and enforce the structural invariants that the platform depends on:

1. Every scanner has a non-empty ``scanner_name``.
2. Every scanner declares at least one ``supported_input_types``.
3. ``supports()`` returns True for each declared input type.
4. ``_do_scan`` is abstract and raises ``NotImplementedError`` only on
   ``BaseOsintScanner`` itself, not on concrete subclasses.
5. ``scan()`` with a mocked ``_do_scan`` returns a ``ScanResult`` with the
   correct scanner_name, input_value, and a non-null ID.
6. Cache key includes the input type — two calls with the same value but
   different input types produce different cache keys. (#4)
7. Circuit breaker open state causes scan() to return FAILED without calling
   _do_scan. (#3)
8. Failed scans (exception from _do_scan) are NOT written to cache. (#10)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.circuit_breaker import CircuitBreaker
from src.core.domain.entities.types import ScanInputType, ScanStatus


# ---------------------------------------------------------------------------
# Minimal concrete scanner for testing the base class behaviour
# ---------------------------------------------------------------------------

class _StubScanner(BaseOsintScanner):
    scanner_name = "stub_test"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP})

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return {"found": True, "data": input_value}


# ---------------------------------------------------------------------------
# Contract: every registered scanner
# ---------------------------------------------------------------------------

def test_all_scanners_have_name_and_input_types() -> None:
    """Every scanner in the default registry must have a non-empty name and
    at least one supported input type. (#29)"""
    from src.adapters.scanners.registry import get_default_registry

    registry = get_default_registry()
    scanners = registry.get_all()
    assert scanners, "Registry must contain at least one scanner"

    for scanner in scanners:
        assert scanner.scanner_name, f"Scanner {type(scanner).__name__} has empty scanner_name"
        assert scanner.supported_input_types, (
            f"Scanner {scanner.scanner_name} has empty supported_input_types"
        )
        for input_type in scanner.supported_input_types:
            assert scanner.supports(input_type), (
                f"Scanner {scanner.scanner_name} does not support declared type {input_type}"
            )


def test_no_duplicate_scanner_names() -> None:
    """Scanner names must be unique across the registry. (#29)"""
    from src.adapters.scanners.registry import get_default_registry

    registry = get_default_registry()
    names = [s.scanner_name for s in registry.get_all()]
    duplicates = [n for n in set(names) if names.count(n) > 1]
    assert not duplicates, f"Duplicate scanner names found: {duplicates}"


# ---------------------------------------------------------------------------
# Contract: base scanner behaviour (using the stub)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_returns_result_with_correct_metadata() -> None:
    """scan() must return a ScanResult with correct scanner_name and input_value. (#30)"""
    scanner = _StubScanner()
    result = await scanner.scan("example.com", ScanInputType.DOMAIN)

    assert result.scanner_name == "stub_test"
    assert result.input_value == "example.com"
    assert result.id is not None
    assert isinstance(result.id, UUID)
    assert result.status == ScanStatus.SUCCESS


@pytest.mark.asyncio
async def test_cache_key_includes_input_type() -> None:
    """Cache keys must differ for the same value with different input types. (#4)"""
    scanner = _StubScanner()
    key_domain = scanner._cache_key("8.8.8.8", ScanInputType.DOMAIN)
    key_ip = scanner._cache_key("8.8.8.8", ScanInputType.IP)
    assert key_domain != key_ip, "Cache keys must differ when input_type differs"


@pytest.mark.asyncio
async def test_circuit_breaker_open_skips_do_scan() -> None:
    """When the circuit breaker is open, _do_scan must not be called. (#3)"""
    cb = MagicMock(spec=CircuitBreaker)
    cb.async_is_open = AsyncMock(return_value=True)

    scanner = _StubScanner(circuit_breaker=cb)
    scanner._do_scan = AsyncMock()  # type: ignore[method-assign]

    result = await scanner.scan("example.com", ScanInputType.DOMAIN)

    scanner._do_scan.assert_not_called()
    assert result.status == ScanStatus.FAILED
    assert "circuit breaker" in (result.error_message or "").lower()


@pytest.mark.asyncio
async def test_failed_scan_is_not_cached() -> None:
    """A scan that raises an exception must not write anything to the cache. (#10)"""
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    scanner = _StubScanner(cache=mock_cache)

    async def _failing_scan(value: str, input_type: ScanInputType) -> dict[str, Any]:
        raise RuntimeError("external API unavailable")

    scanner._do_scan = _failing_scan  # type: ignore[method-assign]

    result = await scanner.scan("example.com", ScanInputType.DOMAIN)

    mock_cache.set.assert_not_called()
    assert result.status == ScanStatus.FAILED


@pytest.mark.asyncio
async def test_successful_scan_is_cached() -> None:
    """A successful scan with non-empty raw_data must be written to cache."""
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()

    scanner = _StubScanner(cache=mock_cache)
    result = await scanner.scan("example.com", ScanInputType.DOMAIN)

    mock_cache.set.assert_called_once()
    assert result.status == ScanStatus.SUCCESS


@pytest.mark.asyncio
async def test_cache_hit_returns_stable_id() -> None:
    """Repeated cache hits for the same key must return a stable (non-random) ID. (#9)"""
    scanner = _StubScanner()

    # Simulate a cache entry written with an explicit _result_id
    import json
    stored_id = "12345678-1234-5678-1234-567812345678"
    cache_data = {"found": True, "_result_id": stored_id, "_extracted_identifiers": []}
    compressed = _StubScanner._compress(cache_data)

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=compressed)
    scanner._cache = mock_cache

    result1 = await scanner.scan("example.com", ScanInputType.DOMAIN)
    result2 = await scanner.scan("example.com", ScanInputType.DOMAIN)

    assert str(result1.id) == stored_id
    assert result1.id == result2.id


@pytest.mark.asyncio
async def test_compress_decompress_roundtrip() -> None:
    """_compress / _decompress must be a lossless roundtrip for any dict. (#16)"""
    data = {"key": "value", "nested": {"a": 1, "b": [1, 2, 3]}}
    compressed = _StubScanner._compress(data)
    assert isinstance(compressed, bytes)
    recovered = _StubScanner._decompress(compressed)
    assert recovered == data


@pytest.mark.asyncio
async def test_compress_decompress_large_payload() -> None:
    """Large payloads (> 10 KB) must be zlib-compressed and recoverable."""
    large_data = {"results": ["x" * 100] * 200}  # ~20 KB
    compressed = _StubScanner._compress(large_data)
    assert len(compressed) < len(str(large_data).encode()), "Large payload should be smaller after compression"
    recovered = _StubScanner._decompress(compressed)
    assert recovered == large_data
