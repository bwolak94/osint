"""Base scanner implementing the Template Method pattern."""

import asyncio
import hashlib
import json
import time
import uuid
import zlib
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.adapters.scanners.circuit_breaker import CircuitBreaker
from src.adapters.scanners.exceptions import (
    RateLimitError,
    ScanAuthError,
    ScannerNotFoundError,
    ScannerQuotaExceededError,
    ScannerUnavailableError,
)
from src.adapters.scanners.metrics import record_circuit_breaker_open, record_scan_duration
from src.core.domain.entities.scan_result import ScanResult
from src.core.domain.entities.types import ScanInputType, ScanStatus
from src.core.ports.cache import ICache
from src.utils.time import utcnow

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants — defined after imports so module structure is clean. (#14)
# ---------------------------------------------------------------------------

_COMPRESSION_THRESHOLD = 10_240  # bytes — compress cache payloads larger than 10 KB
# Magic prefix bytes distinguish compressed from plain JSON in the cache.
_MAGIC_COMPRESSED = b"\x01"
_MAGIC_PLAIN = b"\x00"

# Optional OpenTelemetry tracing — degrades gracefully if library not installed. (#21)
try:
    from opentelemetry import trace as _otel_trace
    _tracer = _otel_trace.get_tracer("osint.scanners")
    _HAS_OTEL = True
except ImportError:
    _tracer = None  # type: ignore[assignment]
    _HAS_OTEL = False


def _redact(value: str) -> str:
    """Replace all but the trailing 4 chars with asterisks.

    Prevents raw scan targets (emails, IPs) from leaking into production logs
    while keeping enough context to identify the request. (#13)
    """
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


class BaseOsintScanner(ABC):
    """Abstract base scanner with caching, circuit breaker, and structured logging.

    Subclasses only need to implement `_do_scan` with their specific logic.
    The `scan` method handles cross-cutting concerns:
    1. Cache lookup
    2. Quota pre-check
    3. Circuit breaker check
    4. Timeout enforcement
    5. Delegation to `_do_scan`
    6. Deduplication via content hash
    7. Error handling and metrics

    Class-level attributes to override in subclasses
    ------------------------------------------------
    scanner_name : str
        Unique registry identifier.
    supported_input_types : frozenset[ScanInputType]
        Input types this scanner handles.
    cache_ttl : int
        Seconds to cache results (default 24 h).
    scan_timeout : int
        Hard timeout in seconds (default 120 s).
    source_confidence : float
        Base confidence weight for this source (0.0–1.0).  Higher means the
        data from this scanner is considered more reliable.  Default 0.5.
    """

    scanner_name: str
    supported_input_types: frozenset[ScanInputType]
    cache_ttl: int = 86400  # Default: 24 hours
    volatile_cache_ttl: int = 300  # Short TTL (5 min) for time-sensitive data. (#17)
    scan_timeout: int = 120  # Seconds before asyncio.wait_for raises TimeoutError
    source_confidence: float = 0.5  # Source reliability weight (0.0 – 1.0)

    def __init__(self, circuit_breaker: CircuitBreaker | None = None, cache: ICache | None = None) -> None:
        self._circuit_breaker = circuit_breaker or CircuitBreaker(name=self.scanner_name)
        self._cache = cache
        # Cache settings at construction time — avoids repeated get_settings() calls
        # inside hot-path exception handlers. (#1)
        from src.config import get_settings
        self._settings = get_settings()

    def supports(self, input_type: ScanInputType) -> bool:
        return input_type in self.supported_input_types

    def _cache_key(self, input_value: str, input_type: ScanInputType) -> str:
        """Build a cache key that includes the input type to prevent collisions.

        Without input_type, the same string (e.g. "8.8.8.8") used as both an
        IP address and a domain would share a cache entry across scanners that
        support multiple input types. (#4)
        """
        digest = hashlib.sha256(input_value.encode()).hexdigest()
        return f"{self.scanner_name}:{input_type.value}:{digest}"

    @staticmethod
    def _compress(data: dict[str, Any]) -> bytes:
        """Serialize and optionally compress in a single JSON pass.

        Returns bytes with a single magic prefix byte:
        - ``\\x01`` + zlib.compress(json_bytes) when payload exceeds the threshold
        - ``\\x00`` + json_bytes otherwise

        This eliminates the previous double-serialisation where the dict was
        JSON-encoded once for size measurement and then left as-is for the cache
        layer to serialize again. (#16)
        """
        raw = json.dumps(data).encode()
        if len(raw) > _COMPRESSION_THRESHOLD:
            return _MAGIC_COMPRESSED + zlib.compress(raw, level=6)
        return _MAGIC_PLAIN + raw

    @staticmethod
    def _decompress(value: Any) -> dict[str, Any]:
        """Decompress a potentially compressed cache value."""
        if isinstance(value, (bytes, bytearray)):
            if value[:1] == _MAGIC_COMPRESSED:
                return json.loads(zlib.decompress(value[1:]))
            if value[:1] == _MAGIC_PLAIN:
                return json.loads(value[1:])
            # Legacy entries written before the magic-byte scheme — try zlib first
            try:
                return json.loads(zlib.decompress(value))
            except Exception:
                return json.loads(value)
        return value  # type: ignore[return-value]

    # ── Dry-run support ───────────────────────────────────────────────────────

    def dry_run_params(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        """Return the query parameters that *would* be sent to the external API
        without actually making the call.  Used for quota estimation.

        Subclasses should override this to expose meaningful params; the default
        returns a minimal description so the base class always works.
        """
        return {
            "scanner": self.scanner_name,
            "input_value": input_value,
            "input_type": input_type.value,
            "cache_ttl": self.cache_ttl,
            "timeout": self.scan_timeout,
        }

    # ── Content-hash deduplication ────────────────────────────────────────────

    @staticmethod
    def _content_hash(raw_data: dict[str, Any]) -> str:
        """Stable SHA-256 of the raw result payload (excludes meta keys)."""
        clean = {k: v for k, v in raw_data.items() if not k.startswith("_")}
        serialised = json.dumps(clean, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()

    async def scan(
        self,
        input_value: str,
        input_type: ScanInputType,
        investigation_id: UUID | None = None,
        cache_ttl: int | None = None,
        dry_run: bool = False,
    ) -> ScanResult:
        """Execute a scan with caching, timeout, and circuit breaker protection.

        Args:
            input_value: The entity to scan (IP, email, domain, …).
            input_type: The semantic type of `input_value`.
            investigation_id: Associates the result with an investigation.
            cache_ttl: Override the scanner's default cache TTL.
            dry_run: When *True*, skip the external call entirely and return a
                stub result containing only the would-be query parameters.  No
                quota is consumed and no circuit breaker state is affected.
        """
        inv_id = investigation_id or uuid4()

        # ── Dry-run short-circuit ─────────────────────────────────────────────
        if dry_run:
            params = self.dry_run_params(input_value, input_type)
            log.debug("dry_run", scanner=self.scanner_name, input=_redact(input_value))
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.SUCCESS,
                raw_data={"_dry_run": True, **params},
                extracted_identifiers=[],
                duration_ms=0,
                created_at=utcnow(),
            )

        # Cache key now includes input_type to prevent cross-type collisions (#4)
        cache_key = self._cache_key(input_value, input_type)
        effective_ttl = cache_ttl if cache_ttl is not None else self.cache_ttl

        # 1. Cache check
        if self._cache is not None:
            cached_raw = await self._cache.get(cache_key)
            if cached_raw is not None:
                cached = self._decompress(cached_raw)
                log.debug("cache_hit", scanner=self.scanner_name, input=_redact(input_value))
                cached_id = cached.get("_result_id")
                if cached_id:
                    result_id = UUID(cached_id)
                else:
                    # Deterministic fallback — stable UUID derived from cache key so
                    # repeated cache hits for old entries always return the same ID
                    # rather than a fresh uuid4() on every call. (#9)
                    result_id = uuid.UUID(hashlib.md5(cache_key.encode()).hexdigest())
                return ScanResult(
                    id=result_id,
                    investigation_id=inv_id,
                    scanner_name=self.scanner_name,
                    input_value=input_value,
                    status=ScanStatus.SUCCESS,
                    raw_data=cached,
                    extracted_identifiers=cached.get("_extracted_identifiers", []),
                    duration_ms=0,
                    created_at=utcnow(),
                )

        # 2. Circuit breaker check (async — Redis-backed)
        if await self._circuit_breaker.async_is_open():
            log.warning("circuit_breaker_open", scanner=self.scanner_name)
            record_circuit_breaker_open(self.scanner_name)  # (#37)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=0,
                created_at=utcnow(),
                error_message=f"Scanner {self.scanner_name} is temporarily unavailable (circuit breaker open)",
            )

        # 3. Execute scan with timeout, wrapped in OTel span when available. (#21)
        start = time.monotonic()
        try:
            if _HAS_OTEL and _tracer is not None:
                with _tracer.start_as_current_span(
                    f"scanner.{self.scanner_name}",
                    attributes={"scanner.name": self.scanner_name, "scanner.input_type": input_type.value},
                ):
                    raw_data = await asyncio.wait_for(
                        self._do_scan(input_value, input_type),
                        timeout=self.scan_timeout,
                    )
            else:
                raw_data = await asyncio.wait_for(
                    self._do_scan(input_value, input_type),
                    timeout=self.scan_timeout,
                )
            await self._circuit_breaker.async_record_success()
            duration_ms = int((time.monotonic() - start) * 1000)
            record_scan_duration(self.scanner_name, duration_ms / 1000.0)

            extracted = self._extract_identifiers(raw_data)
            if not extracted:
                log.debug(
                    "no_identifiers_extracted",
                    scanner=self.scanner_name,
                    input=_redact(input_value),
                )

            # Confidence score: scanner's base weight scaled by result richness
            confidence = self._compute_confidence(raw_data, extracted)

            result_id = uuid4()

            # Content hash is only meaningful for non-empty results; skip the
            # json.dumps overhead when raw_data is empty. (#17)
            content_hash = self._content_hash(raw_data) if raw_data else ""

            result = ScanResult(
                id=result_id,
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.SUCCESS,
                raw_data=raw_data,
                extracted_identifiers=extracted,
                duration_ms=duration_ms,
                created_at=utcnow(),
            )

            # Only cache successful, non-empty results. Empty raw_data payloads
            # (e.g. a scanner that found nothing) are cheap to re-run and not
            # worth occupying cache space. (#10)
            if self._cache is not None and raw_data:
                cache_data = {
                    **raw_data,
                    "_extracted_identifiers": extracted,
                    "_result_id": str(result_id),
                    "_confidence": confidence,
                    "_content_hash": content_hash,
                }
                await self._cache.set(cache_key, self._compress(cache_data), ttl=effective_ttl)

            log.info(
                "scan_completed",
                scanner=self.scanner_name,
                input=_redact(input_value),  # Redact raw scan target from production logs (#13)
                duration_ms=duration_ms,
                findings=len(extracted),
                confidence=round(confidence, 3),
                content_hash=content_hash[:12] if content_hash else "",
            )
            return result

        except asyncio.TimeoutError:
            await self._circuit_breaker.async_record_failure(f"Timeout after {self.scan_timeout}s")
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error("scan_timeout", scanner=self.scanner_name, timeout=self.scan_timeout)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=utcnow(),
                error_message=f"Scan timed out after {self.scan_timeout}s",
            )

        except ScannerNotFoundError:
            # Target not found is a clean non-result — don't trip the CB
            duration_ms = int((time.monotonic() - start) * 1000)
            log.info("scan_not_found", scanner=self.scanner_name)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.SUCCESS,
                raw_data={"_not_found": True},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=utcnow(),
            )

        except ScanAuthError as exc:
            # Auth errors are permanent — open the circuit breaker immediately
            await self._circuit_breaker.async_record_failure(str(exc))
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error("scan_auth_error", scanner=self.scanner_name)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=utcnow(),
                error_message=f"Authentication failed for {self.scanner_name} — check API key",
            )

        except ScannerQuotaExceededError as exc:
            # Quota exhausted is not the scanner's fault — don't trip the CB
            duration_ms = int((time.monotonic() - start) * 1000)
            log.warning("scan_quota_exceeded", scanner=self.scanner_name)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=utcnow(),
                error_message=str(exc),
            )

        except RateLimitError as exc:
            # Use settings cached at construction time — avoids get_settings() in
            # a hot exception handler. (#1)
            if self._settings.scanner_rate_limit_counts_as_failure:
                await self._circuit_breaker.async_record_failure()
            duration_ms = int((time.monotonic() - start) * 1000)
            retry_info = f" (retry after {exc.retry_after}s)" if exc.retry_after else ""
            log.warning("scan_rate_limited", scanner=self.scanner_name)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.RATE_LIMITED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=utcnow(),
                error_message=f"Rate limited by external service{retry_info}",
            )

        except Exception as exc:
            await self._circuit_breaker.async_record_failure(str(exc))
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error("scan_failed", scanner=self.scanner_name, error=str(exc))
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=utcnow(),
                error_message=str(exc),
            )

    @abstractmethod
    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        """Perform the actual scan. Subclasses implement this."""
        ...

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        """Extract new identifiers from raw scan data. Override in subclasses."""
        return raw_data.get("extracted_identifiers", [])

    def _compute_confidence(self, raw_data: dict[str, Any], extracted: list[str]) -> float:
        """Compute a confidence score (0.0–1.0) for this scan result.

        The default formula weights the scanner's source reliability against
        result richness (number of unique extracted identifiers).  Subclasses
        may override for domain-specific logic.

        Formula:
            confidence = source_confidence * richness_factor

        Where richness_factor = min(1.0, len(extracted) / 10) so a result with
        10+ identifiers scores the scanner's full source_confidence, and an
        empty result scores 0.
        """
        if not raw_data or raw_data.get("_stub") or raw_data.get("_not_found"):
            return 0.0
        richness = min(1.0, len(extracted) / 10)
        return round(self.source_confidence * (0.3 + 0.7 * richness), 4)
