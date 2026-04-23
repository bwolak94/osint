"""Qdrant async client factory.

Provides a single-instance QdrantAsyncClient constructed from application
settings.  Consumers import `get_qdrant_client()` and call it lazily —
never import the client directly to keep testability clean.

Qdrant 2026 (Gridstore storage) is configured via:
  QDRANT_URL  — HTTP endpoint (e.g. "http://qdrant:6333")
  QDRANT_API_KEY — optional, for Qdrant Cloud
"""

from __future__ import annotations

import structlog
from qdrant_client import AsyncQdrantClient

from src.config import get_settings

log = structlog.get_logger(__name__)

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    """Return the singleton Qdrant async client.

    Initialised lazily on first call.  Thread-safe because FastAPI's
    event loop is single-threaded.
    """
    global _client  # noqa: PLW0603
    if _client is None:
        settings = get_settings()
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=10,
        )
        log.info("qdrant_client_initialized", url=settings.qdrant_url)
    return _client


async def close_qdrant_client() -> None:
    """Gracefully close the Qdrant client on application shutdown."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.close()
        _client = None
        log.info("qdrant_client_closed")
