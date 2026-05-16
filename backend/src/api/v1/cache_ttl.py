"""Cache TTL management — view and override per-scanner cache TTL settings.

GET  /api/v1/cache/ttl-config    — list current TTL config per scanner
POST /api/v1/cache/ttl-config    — update TTL for a scanner
POST /api/v1/cache/flush/{scanner_name} — flush cache for a scanner
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["cache-management"])

_DEFAULT_TTL = 3600
_MIN_TTL = 60
_MAX_TTL = 604800
_OVERRIDES_KEY = "cache:ttl_overrides"


class TTLConfig(BaseModel):
    scanner_name: str
    ttl_seconds: int
    source: str  # "default" or "override"


class TTLUpdateRequest(BaseModel):
    scanner_name: str
    ttl_seconds: int

    @field_validator("ttl_seconds")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        if v < _MIN_TTL:
            raise ValueError(f"ttl_seconds must be >= {_MIN_TTL}")
        if v > _MAX_TTL:
            raise ValueError(f"ttl_seconds must be <= {_MAX_TTL}")
        return v


class TTLConfigListResponse(BaseModel):
    scanners: list[TTLConfig]
    default_ttl: int


class FlushResponse(BaseModel):
    scanner_name: str
    keys_deleted: int
    status: str


@router.get("/cache/ttl-config", response_model=TTLConfigListResponse)
async def list_ttl_config(
    _: Annotated[User, Depends(get_current_user)],
) -> TTLConfigListResponse:
    """List current TTL configuration for all registered scanners."""
    from src.adapters.scanners.registry import get_default_registry

    try:
        registry = get_default_registry()
        scanner_names = list(registry._scanners.keys()) if hasattr(registry, "_scanners") else []
    except Exception:
        scanner_names = []

    overrides: dict[str, str] = {}
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        overrides = await redis_client.hgetall(_OVERRIDES_KEY) or {}
        await redis_client.aclose()
    except Exception as exc:
        log.debug("cache_ttl_redis_error", error=str(exc))

    configs: list[TTLConfig] = []
    for name in scanner_names:
        if name in overrides:
            configs.append(TTLConfig(
                scanner_name=name,
                ttl_seconds=int(overrides[name]),
                source="override",
            ))
        else:
            configs.append(TTLConfig(
                scanner_name=name,
                ttl_seconds=_DEFAULT_TTL,
                source="default",
            ))

    return TTLConfigListResponse(scanners=configs, default_ttl=_DEFAULT_TTL)


@router.post("/cache/ttl-config", response_model=TTLConfig)
async def update_ttl_config(
    body: TTLUpdateRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> TTLConfig:
    """Override TTL for a specific scanner. Stored in Redis hash."""
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        await redis_client.hset(_OVERRIDES_KEY, body.scanner_name, str(body.ttl_seconds))
        await redis_client.aclose()
    except Exception as exc:
        log.warning("cache_ttl_update_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    return TTLConfig(
        scanner_name=body.scanner_name,
        ttl_seconds=body.ttl_seconds,
        source="override",
    )


@router.post("/cache/flush/{scanner_name}", response_model=FlushResponse)
async def flush_scanner_cache(
    scanner_name: str,
    _: Annotated[User, Depends(get_current_user)],
) -> FlushResponse:
    """Delete all cached scan results for a given scanner."""
    deleted = 0
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        pattern = f"scanner:{scanner_name}:*"
        keys = await redis_client.keys(pattern)
        if keys:
            deleted = await redis_client.delete(*keys)
        await redis_client.aclose()
    except Exception as exc:
        log.warning("cache_flush_failed", scanner=scanner_name, error=str(exc))
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    return FlushResponse(
        scanner_name=scanner_name,
        keys_deleted=deleted,
        status="flushed",
    )
