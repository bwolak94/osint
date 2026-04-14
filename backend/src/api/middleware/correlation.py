"""Correlation ID middleware.

Generates a UUID per request and binds it to the structlog context
so all log entries within the request share the same correlation ID.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique correlation ID to each request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Use an existing header value if provided, otherwise generate one
        correlation_id = request.headers.get(CORRELATION_HEADER, str(uuid.uuid4()))

        # Bind the correlation ID to structlog context vars
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
