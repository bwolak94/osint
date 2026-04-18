"""Tests for investigation fork endpoints."""

import pytest
from unittest.mock import MagicMock


class TestInvestigationForkEndpoints:
    async def test_fork_investigation(self):
        from src.api.v1.investigations.fork import fork_investigation, ForkRequest

        mock_user = MagicMock()
        body = ForkRequest(reason="Explore different lead", include_results=True)
        result = await fork_investigation(
            investigation_id="parent-123",
            body=body,
            current_user=mock_user,
        )
        assert result.parent_investigation_id == "parent-123"
        assert result.child_investigation_id
        assert result.fork_reason == "Explore different lead"

    async def test_list_forks_empty(self):
        from src.api.v1.investigations.fork import list_forks

        mock_user = MagicMock()
        result = await list_forks(investigation_id="parent-123", current_user=mock_user)
        assert result.forks == []
        assert result.total == 0
