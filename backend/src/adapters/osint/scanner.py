"""Stub OSINT scanner implementation.

This is a placeholder for a Playwright-based scanning adapter.
"""

from typing import Any
from uuid import UUID

import structlog

from src.core.ports.osint_scanner import IOsintScanner

log = structlog.get_logger()


class StubOsintScanner(IOsintScanner):
    """Stub scanner that returns placeholder results.

    Replace with a real Playwright-based implementation for production use.
    """

    async def scan(self, identity_id: UUID, query: str, depth: int = 1) -> dict[str, Any]:
        """Return stub scan results."""
        log.info(
            "Stub OSINT scan invoked",
            identity_id=str(identity_id),
            query=query,
            depth=depth,
        )

        # Placeholder response structure
        return {
            "identity_id": str(identity_id),
            "query": query,
            "depth": depth,
            "nodes": [],
            "raw_data": {},
            "status": "stub",
        }
