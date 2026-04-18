"""Tests for investigation diff."""

import pytest
from unittest.mock import MagicMock


class TestInvestigationDiffEndpoints:
    @pytest.mark.asyncio
    async def test_get_diff(self):
        from src.api.v1.investigation_diff import get_investigation_diff

        result = await get_investigation_diff(
            investigation_id="inv-1",
            version_a="v1",
            version_b="v2",
            current_user=MagicMock(),
        )
        assert result.changes == []
        assert result.added_results == 0
        assert result.version_a == "v1"
        assert result.version_b == "v2"

    @pytest.mark.asyncio
    async def test_list_versions(self):
        from src.api.v1.investigation_diff import list_investigation_versions

        result = await list_investigation_versions(
            investigation_id="inv-1", current_user=MagicMock()
        )
        assert result["versions"] == []
        assert result["investigation_id"] == "inv-1"
