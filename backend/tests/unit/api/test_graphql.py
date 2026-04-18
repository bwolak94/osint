"""Tests for GraphQL endpoint."""
import pytest
from unittest.mock import MagicMock


class TestGraphQLEndpoints:
    async def test_graphql_investigations_query(self):
        from src.api.graphql.router import graphql_endpoint
        from src.api.graphql.schema import GraphQLQuery
        mock_user = MagicMock()
        body = GraphQLQuery(query="{ investigations { items { id title } total } }")
        result = await graphql_endpoint(body=body, current_user=mock_user)
        assert result.data is not None
        assert "investigations" in result.data

    async def test_graphql_me_query(self):
        from src.api.graphql.router import graphql_endpoint
        from src.api.graphql.schema import GraphQLQuery
        body = GraphQLQuery(query="{ me { id email } }")
        result = await graphql_endpoint(body=body, current_user=MagicMock())
        assert result.data is not None

    async def test_graphql_schema_endpoint(self):
        from src.api.graphql.router import graphql_schema
        result = await graphql_schema()
        assert "schema" in result
        assert "Investigation" in result["schema"]

    async def test_graphql_unknown_query(self):
        from src.api.graphql.router import graphql_endpoint
        from src.api.graphql.schema import GraphQLQuery
        body = GraphQLQuery(query="{ unknownField }")
        result = await graphql_endpoint(body=body, current_user=MagicMock())
        assert result.errors is not None
