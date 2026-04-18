"""Unit tests for the Dark Web OSINT scanner."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adapters.scanners.darkweb_scanner import DarkWebScanner
from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_text="", status_code=200):
    """Create a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = response_text
    mock_resp.url = "https://ahmia.fi"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestDarkWebScanner:
    """Tests for the Dark Web scanner."""

    async def test_darkweb_with_results(self):
        """A successful search returns mention results."""
        scanner = DarkWebScanner()
        html = '<div class="result">Match 1</div><div class="result">Match 2</div>'
        mock = _mock_httpx_client(response_text=html)

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("test@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["mention_count"] == 2

    async def test_darkweb_supports_multiple_types(self):
        """Dark web scanner supports EMAIL, DOMAIN, and USERNAME."""
        scanner = DarkWebScanner()
        assert scanner.supports(ScanInputType.EMAIL)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_darkweb_no_results(self):
        """An empty search returns found=False."""
        scanner = DarkWebScanner()
        mock = _mock_httpx_client(response_text="<html>No results</html>")

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("nobody@nowhere.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
        assert result.raw_data["mention_count"] == 0
