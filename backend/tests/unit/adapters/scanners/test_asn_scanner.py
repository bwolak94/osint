"""Unit tests for the ASN/BGP OSINT scanner."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adapters.scanners.asn_scanner import ASNScanner
from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200):
    """Create a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = response_data
    mock_resp.text = str(response_data)
    mock_resp.url = "https://api.bgpview.io"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestASNScanner:
    """Tests for the ASN/BGP scanner."""

    async def test_asn_ip_found(self):
        """A successful IP lookup returns ASN information."""
        scanner = ASNScanner()
        mock = _mock_httpx_client({
            "data": {
                "prefixes": [{
                    "prefix": "8.8.8.0/24",
                    "ip": "8.8.8.8",
                    "asn": {
                        "asn": 15169,
                        "name": "GOOGLE",
                        "description": "Google LLC",
                        "country_code": "US",
                    },
                }]
            }
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["asn"] == 15169
        assert result.raw_data["asn_name"] == "GOOGLE"

    async def test_asn_supports_ip_and_domain(self):
        """ASN scanner supports IP_ADDRESS and DOMAIN but not EMAIL."""
        scanner = ASNScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_asn_not_found(self):
        """A 404 response returns found=False."""
        scanner = ASNScanner()
        mock = _mock_httpx_client({}, status_code=404)

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("192.0.2.1", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
