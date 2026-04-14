"""Unit tests for Neo4j graph repository using a mock driver."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.adapters.graph.neo4j_store import Neo4jGraphRepository
from src.core.domain.entities.graph_node import GraphNode
from src.core.domain.entities.graph_edge import GraphEdge
from src.core.domain.entities.types import NodeType, RelationshipType
from src.core.domain.value_objects.confidence_score import ConfidenceScore


def make_node(**overrides) -> GraphNode:
    defaults = {
        "id": uuid4(),
        "investigation_id": uuid4(),
        "node_type": NodeType.PERSON,
        "label": "John Doe",
        "properties": {"age": 30},
        "confidence_score": ConfidenceScore(0.8),
        "sources": frozenset({"holehe"}),
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return GraphNode(**defaults)


def make_edge(**overrides) -> GraphEdge:
    defaults = {
        "id": uuid4(),
        "source_node_id": uuid4(),
        "target_node_id": uuid4(),
        "relationship_type": RelationshipType.OWNS,
        "confidence_score": ConfidenceScore(0.7),
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return GraphEdge(**defaults)


class _AsyncContextManager:
    """Helper to create a proper async context manager from a mock session."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass


class TestNeo4jGraphRepository:
    @pytest.fixture
    def mock_driver(self):
        driver = MagicMock()
        session = AsyncMock()
        result = AsyncMock()
        result.consume = AsyncMock()
        result.single = AsyncMock(return_value=None)
        session.run = AsyncMock(return_value=result)
        driver.session.return_value = _AsyncContextManager(session)
        driver._mock_session = session  # store for test assertions
        return driver

    @pytest.fixture
    def repo(self, mock_driver):
        return Neo4jGraphRepository(mock_driver)

    @pytest.mark.asyncio
    async def test_add_node_calls_merge(self, repo, mock_driver):
        node = make_node()
        result = await repo.add_node(node)
        assert result.id == node.id
        # Verify session.run was called (the MERGE query)
        session = mock_driver._mock_session
        session.run.assert_awaited_once()
        # Check the query contains MERGE
        query = session.run.await_args[0][0]
        assert "MERGE" in query

    @pytest.mark.asyncio
    async def test_add_edge_calls_merge(self, repo, mock_driver):
        edge = make_edge()
        result = await repo.add_edge(edge)
        assert result.id == edge.id
        session = mock_driver._mock_session
        session.run.assert_awaited_once()
        query = session.run.await_args[0][0]
        assert "MERGE" in query or "MATCH" in query

    @pytest.mark.asyncio
    async def test_add_node_passes_correct_params(self, repo, mock_driver):
        node = make_node(label="Alice", node_type=NodeType.EMAIL)
        await repo.add_node(node)
        session = mock_driver._mock_session
        params = session.run.await_args[0][1]
        assert params["label"] == "Alice"
        assert params["node_type"] == "email"
        assert params["label_normalized"] == "alice"

    @pytest.mark.asyncio
    async def test_delete_node_runs_detach_delete(self, repo, mock_driver):
        node_id = uuid4()
        await repo.delete_node(node_id)
        session = mock_driver._mock_session
        session.run.assert_awaited_once()
        query = session.run.await_args[0][0]
        assert "DETACH DELETE" in query
