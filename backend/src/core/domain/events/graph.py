from dataclasses import dataclass
from uuid import UUID

from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class GraphNodeCreated(DomainEvent):
    """Raised when a new node is added to the investigation graph."""
    node_id: UUID = None  # type: ignore[assignment]
    investigation_id: UUID = None  # type: ignore[assignment]
    node_type: str = ""
    label: str = ""


@dataclass(frozen=True)
class GraphEdgeCreated(DomainEvent):
    """Raised when a new edge is added to the investigation graph."""
    edge_id: UUID = None  # type: ignore[assignment]
    source_node_id: UUID = None  # type: ignore[assignment]
    target_node_id: UUID = None  # type: ignore[assignment]
    relationship_type: str = ""
