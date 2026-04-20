"""GraphQL endpoint."""
from typing import Any
import structlog
from fastapi import APIRouter, Depends
from src.api.v1.auth.dependencies import get_current_user
from src.api.graphql.schema import GraphQLQuery, GraphQLResponse, resolve_query, SCHEMA_SDL

log = structlog.get_logger()
router = APIRouter()


@router.post("/graphql", response_model=GraphQLResponse)
async def graphql_endpoint(body: GraphQLQuery, current_user: Any = Depends(get_current_user)) -> GraphQLResponse:
    """Execute a GraphQL query."""
    result = resolve_query(body.query, body.variables)
    return GraphQLResponse(**result)


@router.get("/graphql/schema")
async def graphql_schema() -> dict[str, str]:
    """Return the GraphQL schema SDL."""
    return {"schema": SCHEMA_SDL}
