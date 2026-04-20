"""Tests for graph analytics endpoints."""
import pytest
from unittest.mock import MagicMock


class TestGraphAnalyticsEndpoints:
    @pytest.mark.asyncio
    async def test_get_analytics(self):
        from src.api.v1.graph_analytics import get_graph_analytics

        mock_user = MagicMock()
        result = await get_graph_analytics(investigation_id="inv-1", current_user=mock_user)
        assert result.density == 0.0
        assert result.centrality == []

    @pytest.mark.asyncio
    async def test_get_shortest_path(self):
        from src.api.v1.graph_analytics import get_shortest_path

        mock_user = MagicMock()
        result = await get_shortest_path(investigation_id="inv-1", source="a", target="b", current_user=mock_user)
        assert result.length == 0

    @pytest.mark.asyncio
    async def test_get_timeline(self):
        from src.api.v1.graph_analytics import get_graph_timeline

        mock_user = MagicMock()
        result = await get_graph_timeline(investigation_id="inv-1", current_user=mock_user)
        assert result.snapshots == []

    @pytest.mark.asyncio
    async def test_create_snapshot(self):
        from src.api.v1.graph_analytics import create_graph_snapshot

        mock_user = MagicMock()
        result = await create_graph_snapshot(investigation_id="inv-1", current_user=mock_user)
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_get_diff(self):
        from src.api.v1.graph_analytics import get_graph_diff

        mock_user = MagicMock()
        result = await get_graph_diff(investigation_id="inv-1", from_snapshot="a", to_snapshot="b", current_user=mock_user)
        assert "added_nodes" in result
