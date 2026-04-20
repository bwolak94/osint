"""Tests for saved search alerts."""

import pytest
from unittest.mock import MagicMock


class TestSavedSearchEndpoints:
    @pytest.mark.asyncio
    async def test_list_saved_searches(self):
        from src.api.v1.saved_searches import list_saved_searches

        result = await list_saved_searches(current_user=MagicMock())
        assert result.searches == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_create_saved_search(self):
        from src.api.v1.saved_searches import SavedSearchCreate, create_saved_search

        body = SavedSearchCreate(
            name="Monitor emails", query="type:email", alert_enabled=True
        )
        result = await create_saved_search(body=body, current_user=MagicMock())
        assert result.name == "Monitor emails"
        assert result.alert_enabled is True
        assert result.alert_frequency == "daily"

    @pytest.mark.asyncio
    async def test_run_saved_search(self):
        from src.api.v1.saved_searches import run_saved_search

        result = await run_saved_search(search_id="s-1", current_user=MagicMock())
        assert result["status"] == "executed"
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_delete_saved_search(self):
        from src.api.v1.saved_searches import delete_saved_search

        result = await delete_saved_search(search_id="s-1", current_user=MagicMock())
        assert result["status"] == "deleted"
        assert result["id"] == "s-1"
