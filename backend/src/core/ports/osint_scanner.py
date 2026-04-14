"""Abstract OSINT scanner port."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class IOsintScanner(ABC):
    """Port for OSINT data gathering."""

    @abstractmethod
    async def scan(self, identity_id: UUID, query: str, depth: int = 1) -> dict[str, Any]:
        """Run an OSINT scan for a given query.

        Args:
            identity_id: The identity being investigated.
            query: The search query (email, username, phone, etc.).
            depth: How deep to follow links / related data.

        Returns:
            A dictionary containing the scan results.
        """
        ...
