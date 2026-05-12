"""Rate limiter: global Redis-based middleware + per-route in-memory dependency."""

import time
from collections import defaultdict

import structlog
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from src.config import get_settings

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# In-memory sliding-window rate limiter — FastAPI dependency factory
# ---------------------------------------------------------------------------

_request_counts: dict[str, list[float]] = defaultdict(list)


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Dependency factory for per-route rate limiting by API key or client IP.

    Uses a simple in-memory sliding window. Suitable for public API routes that
    are already authenticated via API key; the key itself is used as the bucket
    identifier so that rate limits are enforced per-consumer rather than per-IP.
    """

    async def check_rate_limit(request: Request) -> None:
        # Prefer API key as bucket identifier; fall back to client IP.
        api_key = request.headers.get("X-API-Key") or (
            request.client.host if request.client else "unknown"
        )
        now = time.time()
        window_start = now - window_seconds

        # Evict timestamps outside the current window.
        _request_counts[api_key] = [
            t for t in _request_counts[api_key] if t > window_start
        ]

        if len(_request_counts[api_key]) >= max_requests:
            log.warning(
                "Per-route rate limit exceeded",
                identifier=api_key,
                limit=max_requests,
                window=window_seconds,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "details": {"limit": max_requests, "window": window_seconds},
                },
            )

        _request_counts[api_key].append(now)

    return check_rate_limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-IP rate limiting using Redis sliding window."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        redis = getattr(request.app.state, "redis", None)

        # If Redis is not available, skip rate limiting
        if redis is None:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"

        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, settings.rate_limit_window_seconds)

            if current > settings.rate_limit_requests:
                log.warning("Rate limit exceeded", client_ip=client_ip, count=current)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                )
        except Exception as exc:
            # If Redis fails, allow the request through
            log.warning("Rate limiter error, allowing request", error=str(exc))

        return await call_next(request)
