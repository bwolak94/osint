"""Unit tests for the Paste Sites OSINT scanner."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adapters.scanners.paste_scanner import PasteSitesScanner
from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200):
    """Create a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_data
    mock_resp.text = str(response_data)
    mock_resp.url = "https://example.com"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


_SAMPLE_PASTES = [
    {"id": "abc123", "title": "Leaked DB", "time": "2024-01-15"},
    {"id": "def456", "title": "Dump 2024", "time": "2024-03-22"},
]


class TestPasteSitesScanner:
    """Tests for the Paste Sites scanner."""

    async def test_paste_search_success(self):
        """A successful psbdmp search returns paste results."""
        scanner = PasteSitesScanner()
        mock_client = _mock_httpx_client(_SAMPLE_PASTES)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("test@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["paste_count"] == 2
        assert len(result.raw_data["pastes"]) == 2
        assert result.raw_data["pastes"][0]["id"] == "abc123"
        assert result.raw_data["pastes"][0]["source"] == "psbdmp"
        assert "paste:abc123" in result.extracted_identifiers
        assert "paste:def456" in result.extracted_identifiers
        assert "google_dork" in result.raw_data

    async def test_paste_supports_email_and_username(self):
        """Paste scanner supports EMAIL and USERNAME but not DOMAIN."""
        scanner = PasteSitesScanner()
        assert scanner.supports(ScanInputType.EMAIL)
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_paste_no_results(self):
        """An empty response returns found=False and a google dork."""
        scanner = PasteSitesScanner()
        mock_client = _mock_httpx_client([])

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nobody@nowhere.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
        assert result.raw_data["paste_count"] == 0
        assert result.raw_data["pastes"] == []
        assert result.extracted_identifiers == []
        assert "google_dork" in result.raw_data
