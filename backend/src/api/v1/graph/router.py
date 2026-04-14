"""Graph query endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from src.api.v1.graph.schemas import AddNodeRequest, SubgraphResponse
from src.adapters.graph.neo4j_store import Neo4jGraphStore
from src.dependencies import get_current_user

router = APIRouter()


def _get_graph_store() -> Neo4jGraphStore:
    """Provide a Neo4j graph store instance."""
    return Neo4jGraphStore()


@router.get("/subgraph/{root_id}", response_model=SubgraphResponse)
async def get_subgraph(
    root_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    depth: int = 2,
) -> SubgraphResponse:
    """Retrieve a subgraph starting from a root node."""
    store = _get_graph_store()
    try:
        result = await store.get_subgraph(root_id, depth=depth)
        return SubgraphResponse(**result)
    finally:
        await store.close()


@router.post("/nodes", status_code=201)
async def add_node(
    body: AddNodeRequest,
    user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, str]:
    """Add a node to the graph."""
    store = _get_graph_store()
    try:
        await store.add_node(
            node_id=body.node_id,
            labels=body.labels,
            properties=body.properties,
        )
        return {"status": "created", "node_id": str(body.node_id)}
    finally:
        await store.close()
