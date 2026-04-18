"""Tests for browser extension API."""
import pytest
from unittest.mock import MagicMock


class TestBrowserExtensionEndpoints:
    @pytest.mark.asyncio
    async def test_quick_scan(self):
        from src.api.v1.browser_extension import extension_quick_scan, QuickScanRequest

        body = QuickScanRequest(
            input_value="example.com", input_type="domain", url="https://test.com"
        )
        result = await extension_quick_scan(body=body, current_user=MagicMock())
        assert result.status == "queued"
        assert result.input_value == "example.com"

    @pytest.mark.asyncio
    async def test_extension_status(self):
        from src.api.v1.browser_extension import extension_status

        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.subscription_tier = "pro"
        result = await extension_status(current_user=mock_user)
        assert result.authenticated is True

    @pytest.mark.asyncio
    async def test_analyze_page(self):
        from src.api.v1.browser_extension import analyze_page

        result = await analyze_page(
            body={"text": "Contact admin@example.com", "url": "https://test.com"},
            current_user=MagicMock(),
        )
        assert len(result.detected_entities) >= 1
