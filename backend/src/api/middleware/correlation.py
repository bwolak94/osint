"""Correlation ID middleware.

Generates a UUID per request and binds it to the structlog context
so all log entries within the request share the same correlation ID.

Handles both X-Correlation-ID (internal tracing) and X-Request-ID
(nginx/load-balancer generated) headers so log correlation works
across the full nginx → api → worker path.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach unique correlation and request IDs to each request.

    Priority order for the correlation ID:
      1. X-Correlation-ID from the incoming request (upstream service set it)
      2. X-Request-ID from the incoming request (nginx set it)
      3. A freshly generated UUID4

    Both IDs are echoed back in the response headers and bound to
    structlog context vars so every log line within the request carries
    them automatically.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Resolve correlation ID
        correlation_id = (
            request.headers.get(CORRELATION_HEADER)
            or request.headers.get(REQUEST_ID_HEADER)
            or str(uuid.uuid4())
        )

        # A request-scoped ID is always freshly generated — it uniquely
        # identifies *this* specific HTTP request within a correlation chain.
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Bind both IDs to structlog context vars (cleared per-request to
        # prevent leakage between concurrent async tasks sharing a thread)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_id=request_id,
        )

        response = await call_next(request)

        # Echo both headers so clients can correlate their own logs
        response.headers[CORRELATION_HEADER] = correlation_id
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
