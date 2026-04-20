"""Tests for TheHive adapter."""

import asyncio
from unittest.mock import MagicMock, patch


class TestTheHiveAdapter:
    def test_test_connection_no_url(self) -> None:
        from src.adapters.integrations.thehive_adapter import TheHiveAdapter

        with patch("src.adapters.integrations.thehive_adapter.get_settings") as mock:
            mock.return_value = MagicMock(thehive_url="", thehive_api_key="")
            adapter = TheHiveAdapter()
            result = asyncio.get_event_loop().run_until_complete(adapter.test_connection())
        assert result["connected"] is False

    def test_test_connection_with_url(self) -> None:
        from src.adapters.integrations.thehive_adapter import TheHiveAdapter

        with patch("src.adapters.integrations.thehive_adapter.get_settings") as mock:
            mock.return_value = MagicMock(thehive_url="http://thehive:9000", thehive_api_key="key")
            adapter = TheHiveAdapter()
            result = asyncio.get_event_loop().run_until_complete(adapter.test_connection())
        assert result["connected"] is True
