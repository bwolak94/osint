"""GraphEdge entity — a directed edge in the investigation knowledge graph."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from src.core.domain.entities.types import RelationshipType
from src.core.domain.value_objects.confidence_score import ConfidenceScore


@dataclass
class GraphEdge:
    """Mutable entity representing a directed relationship between two graph nodes.

    The optional *valid_from* / *valid_to* fields enable temporal queries
    (e.g. "who was CEO in 2022").
    """

    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    relationship_type: RelationshipType
    confidence_score: ConfidenceScore
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
