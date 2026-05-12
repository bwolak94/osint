"""Scanner health registry — tracks liveness of all registered scanners in Redis."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import redis.asyncio as aioredis

log = structlog.get_logger(__name__)

_PREFIX = "scanner_health"
_AUTO_DISABLE_AFTER_OPENS = 3  # Disable a scanner after N consecutive CB opens


class ScannerHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"   # Circuit breaker open but not disabled
    DISABLED = "disabled"   # Admin-disabled or auto-disabled after repeated failures


@dataclass
class ScannerHealth:
    scanner_name: str
    status: ScannerHealthStatus
    consecutive_opens: int
    last_checked: float
    disabled_reason: str | None = None


class ScannerHealthRegistry:
    """Centralised registry that aggregates circuit breaker state across all scanners.

    Stored in Redis so all workers see the same picture.  Falls back to
    in-process dicts when Redis is unavailable.
    """

    def __init__(self, redis_client: "aioredis.Redis | None" = None) -> None:
        self._redis = redis_client
        self._local: dict[str, ScannerHealth] = {}

    def _key(self, scanner: str, field: str) -> str:
        return f"{_PREFIX}:{scanner}:{field}"

    async def _rget(self, scanner: str, field: str, default: str = "") -> str:
        if self._redis is None:
            return default
        try:
            val = await self._redis.get(self._key(scanner, field))
            return val or default
        except Exception:
            return default

    async def _rset(self, scanner: str, field: str, value: str, ex: int = 86400) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(self._key(scanner, field), value, ex=ex)
        except Exception:
            pass

    async def record_circuit_breaker_open(self, scanner_name: str) -> None:
        """Called by the circuit breaker when it opens for a scanner."""
        opens_raw = await self._rget(scanner_name, "consecutive_opens", "0")
        opens = int(opens_raw) + 1
        await self._rset(scanner_name, "consecutive_opens", str(opens))
        await self._rset(scanner_name, "last_open_ts", str(int(time.monotonic())))

        if opens >= _AUTO_DISABLE_AFTER_OPENS:
            await self.disable_scanner(scanner_name, reason=f"Auto-disabled after {opens} consecutive circuit opens")
            log.error("scanner_auto_disabled", scanner=scanner_name, consecutive_opens=opens)
        else:
            await self._rset(scanner_name, "status", ScannerHealthStatus.DEGRADED)

    async def record_circuit_breaker_closed(self, scanner_name: str) -> None:
        """Called when a scanner recovers and its circuit breaker closes."""
        await self._rset(scanner_name, "consecutive_opens", "0")
        current = await self._rget(scanner_name, "status", ScannerHealthStatus.HEALTHY)
        if current != ScannerHealthStatus.DISABLED:
            await self._rset(scanner_name, "status", ScannerHealthStatus.HEALTHY)

    async def disable_scanner(self, scanner_name: str, reason: str = "Manually disabled") -> None:
        await self._rset(scanner_name, "status", ScannerHealthStatus.DISABLED)
        await self._rset(scanner_name, "disabled_reason", reason)

    async def enable_scanner(self, scanner_name: str) -> None:
        await self._rset(scanner_name, "status", ScannerHealthStatus.HEALTHY)
        await self._rset(scanner_name, "consecutive_opens", "0")
        await self._rset(scanner_name, "disabled_reason", "")

    async def is_disabled(self, scanner_name: str) -> bool:
        status = await self._rget(scanner_name, "status", ScannerHealthStatus.HEALTHY)
        return status == ScannerHealthStatus.DISABLED

    async def get_health(self, scanner_name: str) -> ScannerHealth:
        status_raw = await self._rget(scanner_name, "status", ScannerHealthStatus.HEALTHY)
        opens_raw = await self._rget(scanner_name, "consecutive_opens", "0")
        ts_raw = await self._rget(scanner_name, "last_open_ts", "0")
        reason = await self._rget(scanner_name, "disabled_reason", "")
        return ScannerHealth(
            scanner_name=scanner_name,
            status=ScannerHealthStatus(status_raw),
            consecutive_opens=int(opens_raw),
            last_checked=float(ts_raw),
            disabled_reason=reason or None,
        )

    async def get_all_health(self, scanner_names: list[str]) -> list[ScannerHealth]:
        return [await self.get_health(name) for name in scanner_names]
