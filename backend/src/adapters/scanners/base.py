"""Base scanner implementing the Template Method pattern."""

import asyncio
import hashlib
import json
import time
import zlib
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.adapters.scanners.metrics import record_scan_duration

_COMPRESSION_THRESHOLD = 10_240  # bytes — compress cache payloads larger than 10 KB

from src.adapters.scanners.circuit_breaker import CircuitBreaker
from src.adapters.scanners.exceptions import (
    RateLimitError,
    ScanAuthError,
    ScannerNotFoundError,
    ScannerQuotaExceededError,
    ScannerUnavailableError,
)
from src.core.domain.entities.scan_result import ScanResult
from src.core.domain.entities.types import ScanInputType, ScanStatus
from src.core.ports.cache import ICache
from src.utils.time import utcnow

log = structlog.get_logger(__name__)


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
    scan_timeout: int = 120  # Seconds before asyncio.wait_for raises TimeoutError
    source_confidence: float = 0.5  # Source reliability weight (0.0 – 1.0)

    def __init__(self, circuit_breaker: CircuitBreaker | None = None, cache: ICache | None = None) -> None:
        self._circuit_breaker = circuit_breaker or CircuitBreaker(name=self.scanner_name)
        self._cache = cache

    def supports(self, input_type: ScanInputType) -> bool:
        return input_type in self.supported_input_types

    def _cache_key(self, input_value: str) -> str:
        digest = hashlib.sha256(input_value.encode()).hexdigest()
        return f"{self.scanner_name}:{digest}"

    @staticmethod
    def _compress(data: dict[str, Any]) -> bytes | dict[str, Any]:
        """Compress cache payload if it exceeds the threshold."""
        raw = json.dumps(data).encode()
        if len(raw) > _COMPRESSION_THRESHOLD:
            return zlib.compress(raw, level=6)
        return data

    @staticmethod
    def _decompress(value: Any) -> dict[str, Any]:
        """Decompress a potentially compressed cache value."""
        if isinstance(value, (bytes, bytearray)):
            return json.loads(zlib.decompress(value))
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
            log.debug("dry_run", scanner=self.scanner_name, input=input_value)
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

        cache_key = self._cache_key(input_value)
        effective_ttl = cache_ttl if cache_ttl is not None else self.cache_ttl

        # 1. Cache check
        if self._cache is not None:
            cached_raw = await self._cache.get(cache_key)
            if cached_raw is not None:
                cached = self._decompress(cached_raw)
                log.debug("cache_hit", scanner=self.scanner_name, input=input_value)
                # Re-use the cached result's ID for deduplication determinism
                cached_id = cached.get("_result_id")
                return ScanResult(
                    id=UUID(cached_id) if cached_id else uuid4(),
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

        # 3. Execute scan with timeout
        start = time.monotonic()
        try:
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
                    input=input_value,
                )

            # Confidence score: scanner's base weight scaled by result richness
            confidence = self._compute_confidence(raw_data, extracted)

            result_id = uuid4()
            content_hash = self._content_hash(raw_data)
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

            # Cache the result, storing metadata for deterministic cache hits
            if self._cache is not None:
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
                input=input_value,
                duration_ms=duration_ms,
                findings=len(extracted),
                confidence=round(confidence, 3),
                content_hash=content_hash[:12],
            )
            return result

        except asyncio.TimeoutError:
            await self._circuit_breaker.async_record_failure(f"Timeout after {self.scan_timeout}s")
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error("scan_timeout", scanner=self.scanner_name, input=input_value, timeout=self.scan_timeout)
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
            log.info("scan_not_found", scanner=self.scanner_name, input=input_value)
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
            log.error("scan_auth_error", scanner=self.scanner_name, input=input_value)
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
            log.warning("scan_quota_exceeded", scanner=self.scanner_name, input=input_value)
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
            # Rate limiting is transient — do NOT count as circuit breaker failure
            # unless explicitly configured to do so
            from src.config import get_settings
            settings = get_settings()
            if settings.scanner_rate_limit_counts_as_failure:
                await self._circuit_breaker.async_record_failure()
            duration_ms = int((time.monotonic() - start) * 1000)
            retry_info = f" (retry after {exc.retry_after}s)" if exc.retry_after else ""
            log.warning("scan_rate_limited", scanner=self.scanner_name, input=input_value)
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
            log.error("scan_failed", scanner=self.scanner_name, input=input_value, error=str(exc))
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
