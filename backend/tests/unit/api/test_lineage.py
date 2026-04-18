"""Tests for data lineage endpoints."""

import pytest
from unittest.mock import MagicMock


class TestLineageEndpoints:
    @pytest.mark.asyncio
    async def test_get_lineage(self):
        from src.api.v1.lineage import get_lineage

        result = await get_lineage(investigation_id="inv-1", entity_id=None, current_user=MagicMock())
        assert result.entries == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_get_lineage_tree(self):
        from src.api.v1.lineage import get_lineage_tree

        result = await get_lineage_tree(
            investigation_id="inv-1", root_entity_id="entity-1", current_user=MagicMock()
        )
        assert result["root"] == "entity-1"
        assert result["tree"]["entity_id"] == "entity-1"
        assert result["tree"]["children"] == []
