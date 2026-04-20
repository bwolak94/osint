"""Tests for watch list endpoints."""

import pytest
from unittest.mock import MagicMock

from src.api.v1.watchlist import (
    list_watchlist,
    create_watchlist_item,
    update_watchlist_item,
    delete_watchlist_item,
    trigger_watchlist_scan,
    WatchListItemCreate,
)


class TestWatchListEndpoints:
    async def test_list_watchlist_empty(self):
        mock_user = MagicMock()
        result = await list_watchlist(current_user=mock_user)
        assert result.items == []
        assert result.total == 0

    async def test_create_watchlist_item(self):
        mock_user = MagicMock()
        body = WatchListItemCreate(
            name="Monitor example.com",
            input_value="example.com",
            input_type="domain",
            scanners=["dns", "subdomain"],
            schedule_cron="0 */12 * * *",
        )
        result = await create_watchlist_item(body=body, current_user=mock_user)
        assert result.name == "Monitor example.com"
        assert result.input_value == "example.com"
        assert result.is_active is True
        assert result.scan_count == 0

    async def test_delete_watchlist_item(self):
        mock_user = MagicMock()
        result = await delete_watchlist_item(item_id="test-id", current_user=mock_user)
        assert result["status"] == "deleted"

    async def test_trigger_watchlist_scan(self):
        mock_user = MagicMock()
        result = await trigger_watchlist_scan(item_id="test-id", current_user=mock_user)
        assert result["status"] == "triggered"
