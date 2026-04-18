"""Tests for integrations endpoints."""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestIntegrationEndpoints:
    async def test_siem_test_connection(self):
        from src.api.v1.integrations import siem_test_connection
        mock_siem = AsyncMock()
        mock_siem.test_connection = AsyncMock(return_value={"connected": False, "reason": "No endpoint"})
        mock_user = MagicMock()
        result = await siem_test_connection(current_user=mock_user, siem=mock_siem)
        assert result["connected"] is False

    async def test_misp_test_connection(self):
        from src.api.v1.integrations import misp_test_connection
        mock_misp = AsyncMock()
        mock_misp.test_connection = AsyncMock(return_value={"connected": False, "reason": "No URL"})
        mock_user = MagicMock()
        result = await misp_test_connection(current_user=mock_user, misp=mock_misp)
        assert result["connected"] is False

    async def test_siem_forward(self):
        from src.api.v1.integrations import siem_forward, SIEMForwardRequest
        mock_siem = AsyncMock()
        mock_siem.forward_event = AsyncMock(return_value={"status": "skipped"})
        mock_user = MagicMock()
        body = SIEMForwardRequest(event_type="scan_complete", data={"scanner": "shodan"})
        result = await siem_forward(body=body, current_user=mock_user, siem=mock_siem)
        assert result["status"] == "skipped"

    async def test_misp_push(self):
        from src.api.v1.integrations import misp_push, MISPPushRequest
        mock_misp = AsyncMock()
        mock_misp.push_event = AsyncMock(return_value={"status": "skipped"})
        mock_user = MagicMock()
        body = MISPPushRequest(investigation_id="inv-1", title="Test", iocs=[])
        result = await misp_push(body=body, current_user=mock_user, misp=mock_misp)
        assert result["status"] == "skipped"
