"""Simple Redis-based rate limiter middleware."""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import get_settings

log = structlog.get_logger()


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
