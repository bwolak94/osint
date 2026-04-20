"""Unit tests for WaybackScanner with mocked HTTP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestWaybackScanner:
    """Tests for the Wayback Machine scanner."""

    async def test_wayback_success(self):
        """Scanner should parse CDX API response and return structured snapshots."""
        from src.adapters.scanners.wayback_scanner import WaybackScanner

        scanner = WaybackScanner()

        cdx_response = [
            ["timestamp", "original", "statuscode", "mimetype"],
            ["20200115120000", "https://example.com/", "200", "text/html"],
            ["20210320083000", "https://example.com/about", "200", "text/html"],
            ["20220801150000", "https://example.com/contact", "301", "text/html"],
        ]

        mock_client = _mock_httpx_client(cdx_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["snapshot_count"] == 3
        assert len(result.raw_data["snapshots"]) == 3
        assert result.raw_data["first_seen"] == "20200115120000"
        assert result.raw_data["last_seen"] == "20220801150000"

        # Verify snapshot structure
        first_snapshot = result.raw_data["snapshots"][0]
        assert first_snapshot["timestamp"] == "20200115120000"
        assert first_snapshot["url"] == "https://example.com/"
        assert first_snapshot["status"] == "200"
        assert first_snapshot["mimetype"] == "text/html"

        # Verify extracted identifiers
        assert "url:https://example.com/" in result.extracted_identifiers
        assert "url:https://example.com/about" in result.extracted_identifiers
        assert "url:https://example.com/contact" in result.extracted_identifiers

    async def test_wayback_supports_domain_and_url(self):
        """WaybackScanner should support DOMAIN and URL input types."""
        from src.adapters.scanners.wayback_scanner import WaybackScanner

        scanner = WaybackScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_wayback_no_snapshots(self):
        """Scanner should handle case when no snapshots are found."""
        from src.adapters.scanners.wayback_scanner import WaybackScanner

        scanner = WaybackScanner()

        # CDX API returns empty result (only header row or empty)
        mock_client = _mock_httpx_client([])

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent-domain-xyz.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
        assert result.raw_data["snapshot_count"] == 0
        assert result.raw_data["snapshots"] == []
        assert result.raw_data["first_seen"] is None
        assert result.raw_data["last_seen"] is None
        assert result.extracted_identifiers == []
