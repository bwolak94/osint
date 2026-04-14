"""GraphNode entity — a vertex in the investigation knowledge graph."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.domain.entities.types import NodeType
from src.core.domain.value_objects.confidence_score import ConfidenceScore


@dataclass
class GraphNode:
    """Mutable entity representing a node in the OSINT knowledge graph."""

    id: UUID
    investigation_id: UUID
    node_type: NodeType
    label: str
    properties: dict[str, Any]
    confidence_score: ConfidenceScore
    sources: frozenset[str]
    created_at: datetime
