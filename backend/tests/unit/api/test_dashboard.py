"""Tests for dashboard endpoints."""
import pytest
from unittest.mock import MagicMock


class TestDashboardEndpoints:
    @pytest.mark.asyncio
    async def test_get_widgets(self):
        from src.api.v1.dashboard import get_dashboard_widgets
        mock_user = MagicMock()
        result = await get_dashboard_widgets(period="30d", current_user=mock_user)
        assert result.stats.total_investigations == 0
        assert result.scanner_performance == []

    @pytest.mark.asyncio
    async def test_get_stats(self):
        from src.api.v1.dashboard import get_dashboard_stats
        mock_user = MagicMock()
        result = await get_dashboard_stats(current_user=mock_user)
        assert result.total_investigations == 0

    @pytest.mark.asyncio
    async def test_get_scanner_performance(self):
        from src.api.v1.dashboard import get_scanner_performance
        mock_user = MagicMock()
        result = await get_scanner_performance(current_user=mock_user)
        assert result == []
