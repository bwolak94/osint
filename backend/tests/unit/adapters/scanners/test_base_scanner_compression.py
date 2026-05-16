"""Tests for BaseOsintScanner compression, decompression, dry-run, and hashing."""
from __future__ import annotations

import json
import zlib
from typing import Any

import pytest

from src.adapters.scanners.base import BaseOsintScanner, _COMPRESSION_THRESHOLD, _MAGIC_COMPRESSED, _MAGIC_PLAIN
from src.core.domain.entities.types import ScanInputType, ScanStatus


# ---------------------------------------------------------------------------
# Minimal concrete scanner for instantiation
# ---------------------------------------------------------------------------

class MinimalScanner(BaseOsintScanner):
    scanner_name = "test_minimal"
    supported_input_types = frozenset({ScanInputType.DOMAIN})

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return {"found": True}


# ---------------------------------------------------------------------------
# Compress / decompress roundtrip
# ---------------------------------------------------------------------------

class TestCompressDecompress:
    def test_small_payload_uses_plain_magic(self) -> None:
        data = {"key": "value"}
        encoded = BaseOsintScanner._compress(data)
        assert encoded[:1] == _MAGIC_PLAIN

    def test_large_payload_uses_compressed_magic(self) -> None:
        # Build a payload that exceeds _COMPRESSION_THRESHOLD bytes when serialised
        data = {"data": "x" * (_COMPRESSION_THRESHOLD + 1)}
        encoded = BaseOsintScanner._compress(data)
        assert encoded[:1] == _MAGIC_COMPRESSED

    def test_compress_decompress_roundtrip_small(self) -> None:
        original = {"scanner": "test", "found": True, "items": [1, 2, 3]}
        recovered = BaseOsintScanner._decompress(BaseOsintScanner._compress(original))
        assert recovered == original

    def test_compress_decompress_roundtrip_large(self) -> None:
        original = {"data": "a" * (_COMPRESSION_THRESHOLD + 100), "flag": False}
        recovered = BaseOsintScanner._decompress(BaseOsintScanner._compress(original))
        assert recovered == original

    # Legacy path: old entries written with zlib but no magic byte prefix
    def test_decompress_legacy_zlib(self) -> None:
        data = {"legacy": True, "value": 42}
        raw_zlib = zlib.compress(json.dumps(data).encode())  # no magic byte
        recovered = BaseOsintScanner._decompress(raw_zlib)
        assert recovered == data

    # Legacy path: old entries written as plain JSON bytes with no magic byte
    def test_decompress_legacy_plain_json(self) -> None:
        data = {"legacy": "json", "count": 7}
        raw_json = json.dumps(data).encode()  # no magic byte
        recovered = BaseOsintScanner._decompress(raw_json)
        assert recovered == data

    def test_decompress_dict_passthrough(self) -> None:
        """If the cache returns a dict directly (some in-memory caches), pass through."""
        data = {"already": "decoded"}
        recovered = BaseOsintScanner._decompress(data)
        assert recovered == data

    def test_decompress_bytearray_handled(self) -> None:
        original = {"flag": True}
        encoded = bytearray(BaseOsintScanner._compress(original))
        recovered = BaseOsintScanner._decompress(encoded)
        assert recovered == original


# ---------------------------------------------------------------------------
# Content hash stability
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_same_data_same_hash(self) -> None:
        data = {"a": 1, "b": [1, 2, 3]}
        assert BaseOsintScanner._content_hash(data) == BaseOsintScanner._content_hash(data)

    def test_different_data_different_hash(self) -> None:
        assert BaseOsintScanner._content_hash({"a": 1}) != BaseOsintScanner._content_hash({"a": 2})

    def test_private_keys_excluded_from_hash(self) -> None:
        """Metadata keys (prefixed with '_') should not affect the content hash."""
        d1 = {"result": "ok", "_result_id": "uuid-1"}
        d2 = {"result": "ok", "_result_id": "uuid-2"}
        assert BaseOsintScanner._content_hash(d1) == BaseOsintScanner._content_hash(d2)

    def test_key_order_does_not_affect_hash(self) -> None:
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert BaseOsintScanner._content_hash(d1) == BaseOsintScanner._content_hash(d2)


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

class TestDryRun:
    async def test_dry_run_returns_success_without_calling_do_scan(self) -> None:
        scanner = MinimalScanner()
        result = await scanner.scan("example.com", ScanInputType.DOMAIN, dry_run=True)
        assert result.status == ScanStatus.SUCCESS
        assert result.duration_ms == 0
        assert result.raw_data.get("_dry_run") is True

    async def test_dry_run_includes_scanner_name(self) -> None:
        scanner = MinimalScanner()
        result = await scanner.scan("example.com", ScanInputType.DOMAIN, dry_run=True)
        assert result.scanner_name == "test_minimal"

    async def test_dry_run_does_not_affect_circuit_breaker(self) -> None:
        from src.adapters.scanners.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, name="test_dry_run_cb")
        scanner = MinimalScanner(circuit_breaker=cb)

        for _ in range(5):
            await scanner.scan("example.com", ScanInputType.DOMAIN, dry_run=True)

        # Circuit breaker must not have opened
        assert cb.is_open is False
