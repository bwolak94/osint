"""Graph endpoints scoped to an investigation."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.investigations.schemas import (
    AddEdgeRequest,
    AddNodeRequest,
    GraphEdgeSchema,
    GraphMetaSchema,
    GraphNodeSchema,
    GraphResponse,
    PathsResponse,
)
from src.core.domain.entities.user import User

router = APIRouter()


@router.get("/{investigation_id}/graph", response_model=GraphResponse)
async def get_graph(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    depth: int = Query(default=3, ge=1, le=5),
) -> GraphResponse:
    """Return the full knowledge graph for an investigation."""
    # Placeholder — in production, query Neo4j
    return GraphResponse(nodes=[], edges=[], meta=GraphMetaSchema())


@router.get("/{investigation_id}/graph/nodes", response_model=list[GraphNodeSchema])
async def get_graph_nodes(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    node_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[GraphNodeSchema]:
    """List graph nodes with optional type filter."""
    return []


@router.get("/{investigation_id}/graph/edges", response_model=list[GraphEdgeSchema])
async def get_graph_edges(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    edge_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
) -> list[GraphEdgeSchema]:
    """List graph edges with optional type filter."""
    return []


@router.post("/{investigation_id}/graph/nodes", response_model=GraphNodeSchema, status_code=status.HTTP_201_CREATED)
async def add_graph_node(
    investigation_id: UUID,
    body: AddNodeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphNodeSchema:
    """Manually add a node to the investigation graph."""
    from uuid import uuid4
    return GraphNodeSchema(
        id=str(uuid4()), type=body.type, label=body.label,
        properties=body.properties, confidence=1.0, sources=["manual"],
    )


@router.post("/{investigation_id}/graph/edges", response_model=GraphEdgeSchema, status_code=status.HTTP_201_CREATED)
async def add_graph_edge(
    investigation_id: UUID,
    body: AddEdgeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> GraphEdgeSchema:
    """Manually add an edge between two nodes."""
    from uuid import uuid4
    return GraphEdgeSchema(
        id=str(uuid4()), source=body.source_node_id, target=body.target_node_id,
        type=body.type, label=body.label, confidence=1.0,
    )


@router.delete("/{investigation_id}/graph/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_graph_node(
    investigation_id: UUID,
    node_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove a node and its edges from the graph."""
    pass


@router.get("/{investigation_id}/graph/paths", response_model=PathsResponse)
async def find_paths(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    from_node: str = Query(..., alias="from"),
    to_node: str = Query(..., alias="to"),
) -> PathsResponse:
    """Find shortest paths between two nodes."""
    return PathsResponse(paths=[], path_count=0)
