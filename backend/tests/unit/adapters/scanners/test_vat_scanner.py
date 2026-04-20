"""Integration-style tests for VAT scanner with mocked HTTP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.adapters.scanners.playwright_vat import VATStatusScanner
from src.core.domain.entities.types import ScanInputType, ScanStatus


class TestVATScanner:
    async def test_successful_nip_lookup(self):
        scanner = VATStatusScanner()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "subject": {
                    "name": "TEST COMPANY SP. Z O.O.",
                    "nip": "5261040828",
                    "statusVat": "Czynny",
                    "regon": "000331501",
                    "krs": "0000123456",
                    "residenceAddress": None,
                    "workingAddress": "UL. TESTOWA 1, 00-001 WARSZAWA",
                    "accountNumbers": ["12345678901234567890123456"],
                    "registrationLegalDate": "2000-01-01",
                }
            }
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await scanner.scan("5261040828", ScanInputType.NIP)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["name"] == "TEST COMPANY SP. Z O.O."
        assert result.raw_data["status_vat"] == "Czynny"
        assert len(result.raw_data["bank_accounts"]) == 1
        assert len(result.extracted_identifiers) > 0

    async def test_nip_not_found(self):
        scanner = VATStatusScanner()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"subject": None}}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await scanner.scan("0000000000", ScanInputType.NIP)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False


class TestWhoisScanner:
    async def test_successful_domain_lookup(self):
        from src.adapters.scanners.whois_scanner import WhoisScanner
        scanner = WhoisScanner()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "example.com",
            "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]]}],
            "nameservers": [{"ldhName": "ns1.example.com"}, {"ldhName": "ns2.example.com"}],
            "status": ["active"],
            "events": [
                {"eventAction": "registration", "eventDate": "2000-01-01"},
                {"eventAction": "expiration", "eventDate": "2030-01-01"},
            ],
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["registrar"] == "Example Registrar"
        assert len(result.raw_data["nameservers"]) == 2


class TestDNSScanner:
    async def test_successful_dns_lookup(self):
        from src.adapters.scanners.dns_scanner import DNSScanner
        scanner = DNSScanner()

        def mock_get(url, **kwargs):
            rtype = kwargs.get("params", {}).get("type", "A")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if rtype == "A":
                mock_resp.json.return_value = {"Answer": [{"data": "93.184.216.34"}]}
            elif rtype == "MX":
                mock_resp.json.return_value = {"Answer": [{"data": "10 mail.example.com."}]}
            elif rtype == "NS":
                mock_resp.json.return_value = {"Answer": [{"data": "ns1.example.com."}]}
            else:
                mock_resp.json.return_value = {"Answer": []}
            return mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=mock_get)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert "93.184.216.34" in result.raw_data["a_records"]
        assert len(result.extracted_identifiers) > 0
