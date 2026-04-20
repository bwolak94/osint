"""Tests for MISP adapter."""
import pytest
from unittest.mock import MagicMock, patch


class TestMISPAdapter:
    def test_test_connection_no_url(self):
        from src.adapters.integrations.misp_adapter import MISPAdapter
        with patch("src.adapters.integrations.misp_adapter.get_settings") as mock:
            mock.return_value = MagicMock(misp_url="", misp_api_key="", misp_verify_ssl=True)
            adapter = MISPAdapter()
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(adapter.test_connection())
        assert result["connected"] is False

    def test_ioc_to_attribute(self):
        from src.adapters.integrations.misp_adapter import MISPAdapter
        with patch("src.adapters.integrations.misp_adapter.get_settings") as mock:
            mock.return_value = MagicMock(misp_url="", misp_api_key="", misp_verify_ssl=True)
            adapter = MISPAdapter()
        result = adapter._ioc_to_attribute({"type": "ip", "value": "1.2.3.4", "source_scanner": "shodan"})
        assert result["type"] == "ip-dst"
        assert result["value"] == "1.2.3.4"
        assert result["to_ids"] is True
