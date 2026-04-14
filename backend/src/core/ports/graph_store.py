"""Abstract graph store port."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class IGraphStore(ABC):
    """Port for graph database operations."""

    @abstractmethod
    async def add_node(self, node_id: UUID, labels: list[str], properties: dict[str, Any]) -> None:
        """Create or merge a node in the graph."""
        ...

    @abstractmethod
    async def add_edge(
        self,
        source_id: UUID,
        target_id: UUID,
        relationship: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a directed edge between two nodes."""
        ...

    @abstractmethod
    async def get_subgraph(self, root_id: UUID, depth: int = 2) -> dict[str, Any]:
        """Retrieve a subgraph starting from a root node.

        Returns:
            A dict with 'nodes' and 'edges' keys.
        """
        ...
