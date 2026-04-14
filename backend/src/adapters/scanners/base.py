"""Base scanner implementing the Template Method pattern."""

import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.adapters.scanners.circuit_breaker import CircuitBreaker
from src.adapters.scanners.exceptions import RateLimitError, ScannerUnavailableError
from src.core.domain.entities.scan_result import ScanResult
from src.core.domain.entities.types import ScanInputType, ScanStatus
from src.core.ports.cache import ICache

log = structlog.get_logger()


class BaseOsintScanner(ABC):
    """Abstract base scanner with caching, circuit breaker, and structured logging.

    Subclasses only need to implement `_do_scan` with their specific logic.
    The `scan` method handles cross-cutting concerns:
    1. Cache lookup
    2. Circuit breaker check
    3. Delegation to `_do_scan`
    4. Error handling and metrics
    """

    scanner_name: str
    supported_input_types: frozenset[ScanInputType]

    def __init__(self, circuit_breaker: CircuitBreaker | None = None, cache: ICache | None = None) -> None:
        self._circuit_breaker = circuit_breaker or CircuitBreaker(name=self.scanner_name)
        self._cache = cache

    def supports(self, input_type: ScanInputType) -> bool:
        return input_type in self.supported_input_types

    async def scan(self, input_value: str, input_type: ScanInputType, investigation_id: UUID | None = None) -> ScanResult:
        """Execute a scan with caching and circuit breaker protection."""
        inv_id = investigation_id or uuid4()
        cache_key = f"{self.scanner_name}:{hashlib.sha256(input_value.encode()).hexdigest()}"

        # 1. Cache check
        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                log.info("Cache hit", scanner=self.scanner_name, input=input_value)
                return ScanResult(
                    id=uuid4(),
                    investigation_id=inv_id,
                    scanner_name=self.scanner_name,
                    input_value=input_value,
                    status=ScanStatus.SUCCESS,
                    raw_data=cached,
                    extracted_identifiers=cached.get("_extracted_identifiers", []),
                    duration_ms=0,
                    created_at=datetime.now(timezone.utc),
                )

        # 2. Circuit breaker
        if self._circuit_breaker.is_open:
            log.warning("Circuit breaker open", scanner=self.scanner_name)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=0,
                created_at=datetime.now(timezone.utc),
                error_message=f"Scanner {self.scanner_name} is temporarily unavailable (circuit breaker open)",
            )

        # 3. Execute scan
        start = time.monotonic()
        try:
            raw_data = await self._do_scan(input_value, input_type)
            self._circuit_breaker.record_success()
            duration_ms = int((time.monotonic() - start) * 1000)

            extracted = self._extract_identifiers(raw_data)

            result = ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.SUCCESS,
                raw_data=raw_data,
                extracted_identifiers=extracted,
                duration_ms=duration_ms,
                created_at=datetime.now(timezone.utc),
            )

            # Cache the result
            if self._cache is not None:
                cache_data = {**raw_data, "_extracted_identifiers": extracted}
                await self._cache.set(cache_key, cache_data, ttl=86400)

            log.info("Scan completed", scanner=self.scanner_name, input=input_value, duration_ms=duration_ms, findings=len(extracted))
            return result

        except RateLimitError:
            self._circuit_breaker.record_failure()
            duration_ms = int((time.monotonic() - start) * 1000)
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.RATE_LIMITED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=datetime.now(timezone.utc),
                error_message="Rate limited by external service",
            )

        except Exception as exc:
            self._circuit_breaker.record_failure()
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error("Scan failed", scanner=self.scanner_name, input=input_value, error=str(exc))
            return ScanResult(
                id=uuid4(),
                investigation_id=inv_id,
                scanner_name=self.scanner_name,
                input_value=input_value,
                status=ScanStatus.FAILED,
                raw_data={},
                extracted_identifiers=[],
                duration_ms=duration_ms,
                created_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )

    @abstractmethod
    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        """Perform the actual scan. Subclasses implement this."""
        ...

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        """Extract new identifiers from raw scan data. Override in subclasses for custom extraction."""
        return raw_data.get("extracted_identifiers", [])
