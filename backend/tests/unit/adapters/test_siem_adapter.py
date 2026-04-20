"""Tests for SIEM adapter."""
import pytest
from unittest.mock import MagicMock, patch


class TestSIEMAdapter:
    def test_test_connection_no_endpoint(self):
        from src.adapters.integrations.siem_adapter import SIEMAdapter
        with patch("src.adapters.integrations.siem_adapter.get_settings") as mock:
            mock.return_value = MagicMock(siem_endpoint="", siem_type="splunk")
            adapter = SIEMAdapter()
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(adapter.test_connection())
        assert result["connected"] is False

    def test_format_splunk_event(self):
        from src.adapters.integrations.siem_adapter import SIEMAdapter
        with patch("src.adapters.integrations.siem_adapter.get_settings") as mock:
            mock.return_value = MagicMock(siem_endpoint="http://splunk", siem_type="splunk", siem_api_key="key")
            adapter = SIEMAdapter()
        result = adapter._format_event("splunk", "scan_complete", {"scanner": "shodan"})
        assert result["sourcetype"] == "osint_platform"
        assert result["event"]["type"] == "scan_complete"

    def test_get_headers_splunk(self):
        from src.adapters.integrations.siem_adapter import SIEMAdapter
        with patch("src.adapters.integrations.siem_adapter.get_settings") as mock:
            mock.return_value = MagicMock(siem_api_key="test-key", siem_type="splunk")
            adapter = SIEMAdapter()
        headers = adapter._get_headers("splunk")
        assert "Splunk test-key" in headers["Authorization"]
