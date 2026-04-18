"""Unit tests for SubdomainScanner with mocked HTTP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200, text=None):
    """Create a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_data
    mock_resp.text = text if text is not None else str(response_data)
    mock_resp.url = "https://example.com"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestSubdomainScanner:
    """Tests for the Subdomain Enumeration scanner."""

    async def test_subdomain_crtsh_success(self):
        """Scanner should combine and deduplicate subdomains from crt.sh and HackerTarget."""
        from src.adapters.scanners.subdomain_scanner import SubdomainScanner

        scanner = SubdomainScanner()

        crtsh_response = [
            {"common_name": "api.example.com", "name_value": "api.example.com"},
            {"common_name": "mail.example.com", "name_value": "mail.example.com"},
            {"common_name": "www.example.com", "name_value": "www.example.com"},
        ]

        hackertarget_text = "api.example.com,1.2.3.4\ncdn.example.com,5.6.7.8\n"

        # We need different responses for the two GET calls
        crtsh_resp = MagicMock()
        crtsh_resp.status_code = 200
        crtsh_resp.raise_for_status = MagicMock()
        crtsh_resp.json.return_value = crtsh_response
        crtsh_resp.text = str(crtsh_response)

        ht_resp = MagicMock()
        ht_resp.status_code = 200
        ht_resp.raise_for_status = MagicMock()
        ht_resp.json.return_value = {}
        ht_resp.text = hackertarget_text

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[crtsh_resp, ht_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        # api.example.com appears in both sources but should be deduplicated
        assert result.raw_data["subdomain_count"] == 4
        assert "api.example.com" in result.raw_data["subdomains"]
        assert "mail.example.com" in result.raw_data["subdomains"]
        assert "www.example.com" in result.raw_data["subdomains"]
        assert "cdn.example.com" in result.raw_data["subdomains"]
        assert "crt.sh" in result.raw_data["sources_used"]
        assert "hackertarget" in result.raw_data["sources_used"]
        assert "domain:api.example.com" in result.extracted_identifiers

    async def test_subdomain_supports_domain_only(self):
        """SubdomainScanner should only support DOMAIN input type."""
        from src.adapters.scanners.subdomain_scanner import SubdomainScanner

        scanner = SubdomainScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.URL)

    async def test_subdomain_no_results(self):
        """Scanner should handle case when no subdomains are found."""
        from src.adapters.scanners.subdomain_scanner import SubdomainScanner

        scanner = SubdomainScanner()

        crtsh_resp = MagicMock()
        crtsh_resp.status_code = 200
        crtsh_resp.raise_for_status = MagicMock()
        crtsh_resp.json.return_value = []
        crtsh_resp.text = "[]"

        ht_resp = MagicMock()
        ht_resp.status_code = 200
        ht_resp.raise_for_status = MagicMock()
        ht_resp.json.return_value = {}
        ht_resp.text = ""

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[crtsh_resp, ht_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent-domain-xyz.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
        assert result.raw_data["subdomains"] == []
        assert result.raw_data["subdomain_count"] == 0
