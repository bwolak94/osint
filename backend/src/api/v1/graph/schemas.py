"""Graph-related Pydantic schemas."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AddNodeRequest(BaseModel):
    """Request body for adding a graph node."""

    node_id: UUID
    labels: list[str] = ["Node"]
    properties: dict[str, Any] = {}


class GraphNode(BaseModel):
    """Representation of a graph node."""

    id: str
    labels: list[str]
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    """Representation of a graph edge."""

    source: str
    target: str
    type: str
    properties: dict[str, Any] = {}


class SubgraphResponse(BaseModel):
    """Response containing a subgraph of nodes and edges."""

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
