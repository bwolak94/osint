"""Unit tests for threat intelligence and corporate OSINT scanners.

Covers: GreyNoiseScanner, URLhausScanner, ThreatFoxScanner, MalwareBazaarScanner,
CIRLHashlookupScanner, OpenCorporatesScanner, SECEdgarScanner,
OpenSanctionsScanner, GDELTScanner.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.entities.types import ScanInputType, ScanStatus


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_resp(response_data=None, status_code=200, text=None):
    mock_r = MagicMock()
    mock_r.status_code = status_code
    mock_r.raise_for_status = MagicMock()
    mock_r.json.return_value = response_data if response_data is not None else {}
    mock_r.text = text if text is not None else str(response_data)
    mock_r.url = "https://example.com"
    return mock_r


def _mock_httpx(response_data=None, status_code=200, text=None):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.post = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# GreyNoiseScanner
# ---------------------------------------------------------------------------

class TestGreyNoiseScanner:
    """Tests for the GreyNoise IP classification scanner."""

    async def test_scan_noise_ip_with_api_key(self):
        """Known noise IP returns classification=malicious."""
        from src.adapters.scanners.greynoise_scanner import GreyNoiseScanner

        scanner = GreyNoiseScanner()

        community_resp = _mock_resp({
            "ip": "45.33.32.156",
            "noise": True,
            "riot": False,
            "classification": "malicious",
            "name": "Scanner X",
            "link": "https://viz.greynoise.io/ip/45.33.32.156",
            "last_seen": "2024-01-15",
            "message": "This IP is actively scanning the internet",
        })

        stats_resp = _mock_resp({
            "count": 42,
            "complete": True,
            "message": "",
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[community_resp, stats_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.greynoise_scanner.get_settings") as ms:
                ms.return_value.greynoise_api_key = "test_api_key"
                result = await scanner.scan("45.33.32.156", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["noise"] is True
        assert result.raw_data["classification"] == "malicious"

    async def test_scan_clean_ip_internetdb_fallback(self):
        """Without API key, InternetDB fallback used for clean IP."""
        from src.adapters.scanners.greynoise_scanner import GreyNoiseScanner

        scanner = GreyNoiseScanner()

        internetdb_resp = _mock_resp({
            "ip": "8.8.8.8",
            "ports": [53],
            "cpes": [],
            "hostnames": ["dns.google"],
            "tags": [],
            "vulns": [],
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=internetdb_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.greynoise_scanner.get_settings") as ms:
                ms.return_value.greynoise_api_key = ""
                result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["source"] == "internetdb_fallback"

    async def test_scan_not_found_with_api_key(self):
        """404 from GreyNoise Community API returns found=False."""
        from src.adapters.scanners.greynoise_scanner import GreyNoiseScanner

        scanner = GreyNoiseScanner()

        not_found_resp = _mock_resp({}, status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=not_found_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.greynoise_scanner.get_settings") as ms:
                ms.return_value.greynoise_api_key = "test_key"
                result = await scanner.scan("192.0.2.1", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """GreyNoise supports only IP_ADDRESS."""
        from src.adapters.scanners.greynoise_scanner import GreyNoiseScanner

        scanner = GreyNoiseScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """Network exception returns FAILED status."""
        from src.adapters.scanners.greynoise_scanner import GreyNoiseScanner

        scanner = GreyNoiseScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.greynoise_scanner.get_settings") as ms:
                ms.return_value.greynoise_api_key = ""
                result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.FAILED


# ---------------------------------------------------------------------------
# URLhausScanner
# ---------------------------------------------------------------------------

class TestURLhausScanner:
    """Tests for the URLhaus malicious URL database scanner."""

    async def test_scan_malicious_url(self):
        """URL found in URLhaus database returns found=True with threat info."""
        from src.adapters.scanners.urlhaus_scanner import URLhausScanner

        scanner = URLhausScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "is_listed",
            "id": "123456",
            "url_status": "online",
            "threat": "malware_download",
            "tags": ["emotet", "spambot"],
            "blacklists": {"surbl": "listed", "gsb": "not listed"},
            "date_added": "2024-01-01",
            "last_online": "2024-01-15",
            "reporter": "anonymous",
            "payloads": [],
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("http://malicious.example.com/download.exe", ScanInputType.URL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["threat"] == "malware_download"

    async def test_scan_url_not_listed(self):
        """Clean URL returns found=False."""
        from src.adapters.scanners.urlhaus_scanner import URLhausScanner

        scanner = URLhausScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "no_results",
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("https://example.com/clean", ScanInputType.URL)

        assert result.raw_data["found"] is False

    async def test_scan_host_with_malicious_urls(self):
        """Domain scan returns malicious URLs hosted on that domain."""
        from src.adapters.scanners.urlhaus_scanner import URLhausScanner

        scanner = URLhausScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "is_listed",
            "url_count": 2,
            "urls": [
                {
                    "url": "http://badactor.example.com/payload.exe",
                    "url_status": "online",
                    "date_added": "2024-01-01",
                    "threat": "malware_download",
                    "tags": ["loader"],
                },
                {
                    "url": "http://badactor.example.com/shell.php",
                    "url_status": "offline",
                    "date_added": "2023-12-01",
                    "threat": "webshell",
                    "tags": [],
                },
            ],
            "blacklists": {"surbl": "not listed", "gsb": "not listed"},
            "first_seen": "2023-12-01",
            "last_seen": "2024-01-15",
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("badactor.example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is True
        assert result.raw_data["url_count"] == 2
        assert len(result.raw_data["malware_families"]) > 0

    async def test_supports_input_types(self):
        """URLhaus supports URL, DOMAIN, and IP_ADDRESS."""
        from src.adapters.scanners.urlhaus_scanner import URLhausScanner

        scanner = URLhausScanner()
        assert scanner.supports(ScanInputType.URL)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """Network exception returns FAILED status."""
        from src.adapters.scanners.urlhaus_scanner import URLhausScanner

        scanner = URLhausScanner()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("http://malicious.example.com/file", ScanInputType.URL)

        assert result.status == ScanStatus.FAILED

    async def test_extracts_malicious_url_identifiers(self):
        """Malicious URLs from host lookup are extracted as url: identifiers."""
        from src.adapters.scanners.urlhaus_scanner import URLhausScanner

        scanner = URLhausScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "is_listed",
            "url_count": 1,
            "urls": [{
                "url": "http://bad.example.com/evil.exe",
                "url_status": "online",
                "date_added": "2024-01-01",
                "threat": "malware_download",
                "tags": [],
            }],
            "blacklists": {},
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("bad.example.com", ScanInputType.DOMAIN)

        assert "url:http://bad.example.com/evil.exe" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# ThreatFoxScanner
# ---------------------------------------------------------------------------

class TestThreatFoxScanner:
    """Tests for the ThreatFox IOC database scanner."""

    async def test_scan_found_ioc(self):
        """Search returns matching IOC records with malware info."""
        from src.adapters.scanners.threatfox_scanner import ThreatFoxScanner

        scanner = ThreatFoxScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "ok",
            "data": [
                {
                    "id": "ioc_123",
                    "ioc_type": "domain",
                    "ioc": "malicious.example.com",
                    "threat_type": "botnet_cc",
                    "malware_printable": "Emotet",
                    "fk_malware": "",
                    "malware_alias": "Heodo",
                    "confidence_level": 90,
                    "first_seen": "2024-01-01",
                    "last_seen": "2024-01-15",
                    "reference": "https://threatfox.abuse.ch/ioc/123",
                    "tags": ["Emotet", "loader"],
                    "reporter": "researcher_x",
                },
            ],
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("malicious.example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["total_matches"] == 1
        assert "botnet_cc" in result.raw_data["threat_types"]
        assert "Emotet" in result.raw_data["malware_families"]

    async def test_scan_not_found(self):
        """No matching IOCs returns found=False."""
        from src.adapters.scanners.threatfox_scanner import ThreatFoxScanner

        scanner = ThreatFoxScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "no_result",
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("clean.example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert result.raw_data["total_matches"] == 0

    async def test_supports_input_types(self):
        """ThreatFox supports IP_ADDRESS, DOMAIN, and URL."""
        from src.adapters.scanners.threatfox_scanner import ThreatFoxScanner

        scanner = ThreatFoxScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """HTTP error returns FAILED status."""
        from src.adapters.scanners.threatfox_scanner import ThreatFoxScanner

        scanner = ThreatFoxScanner()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.FAILED

    async def test_extracts_identifiers(self):
        """Domain and IP IOCs extracted as typed identifiers."""
        from src.adapters.scanners.threatfox_scanner import ThreatFoxScanner

        scanner = ThreatFoxScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "ok",
            "data": [
                {
                    "id": "1",
                    "ioc_type": "domain",
                    "ioc": "c2.malware.example",
                    "threat_type": "botnet_cc",
                    "malware_printable": "TrickBot",
                    "fk_malware": "",
                    "malware_alias": "",
                    "confidence_level": 75,
                    "first_seen": "2024-01-01",
                    "last_seen": None,
                    "reference": None,
                    "tags": [],
                    "reporter": "anon",
                },
                {
                    "id": "2",
                    "ioc_type": "ip:port",
                    "ioc": "1.2.3.4:4444",
                    "threat_type": "botnet_cc",
                    "malware_printable": "TrickBot",
                    "fk_malware": "",
                    "malware_alias": "",
                    "confidence_level": 80,
                    "first_seen": "2024-01-01",
                    "last_seen": None,
                    "reference": None,
                    "tags": [],
                    "reporter": "anon",
                },
            ],
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("c2.malware.example", ScanInputType.DOMAIN)

        assert "domain:c2.malware.example" in result.extracted_identifiers
        assert "ip:1.2.3.4" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# MalwareBazaarScanner
# ---------------------------------------------------------------------------

class TestMalwareBazaarScanner:
    """Tests for the MalwareBazaar malware sample scanner."""

    async def test_scan_hash_found(self):
        """SHA256 hash returns malware sample metadata."""
        from src.adapters.scanners.malwarebazaar_scanner import MalwareBazaarScanner

        scanner = MalwareBazaarScanner()

        sha256 = "a" * 64  # 64 hex chars = valid SHA256

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "ok",
            "data": [
                {
                    "sha256_hash": sha256,
                    "md5_hash": "b" * 32,
                    "sha1_hash": "c" * 40,
                    "file_name": "malware.exe",
                    "file_type": "exe",
                    "file_type_mime": "application/x-dosexec",
                    "file_size": 204800,
                    "signature": "Emotet",
                    "tags": ["emotet", "loader"],
                    "delivery_method": "email",
                    "first_seen": "2024-01-01",
                    "last_seen": "2024-01-15",
                    "reporter": "researcher",
                    "intelligence": {"clamav": [], "virustotal": {}, "cape_sandbox": {}, "any_run": []},
                    "urls": [],
                }
            ],
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan(sha256, ScanInputType.URL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["total_samples"] == 1

    async def test_scan_hash_not_found(self):
        """Unknown hash returns found=False."""
        from src.adapters.scanners.malwarebazaar_scanner import MalwareBazaarScanner

        scanner = MalwareBazaarScanner()
        sha256 = "f" * 64

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({
            "query_status": "hash_not_found",
        }))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan(sha256, ScanInputType.URL)

        assert result.raw_data["found"] is False

    async def test_scan_signature_search(self):
        """Domain input triggers signature search."""
        from src.adapters.scanners.malwarebazaar_scanner import MalwareBazaarScanner

        scanner = MalwareBazaarScanner()

        sig_resp = _mock_resp({
            "query_status": "ok",
            "data": [
                {
                    "sha256_hash": "d" * 64,
                    "md5_hash": "e" * 32,
                    "sha1_hash": "f" * 40,
                    "file_name": "sample.doc",
                    "file_type": "docx",
                    "file_type_mime": "application/vnd.openxmlformats",
                    "file_size": 102400,
                    "signature": "Trickbot",
                    "tags": ["trickbot"],
                    "delivery_method": "email",
                    "first_seen": "2024-01-01",
                    "last_seen": None,
                    "reporter": "anon",
                    "intelligence": {},
                    "urls": [],
                }
            ],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=sig_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("Trickbot", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is True

    async def test_supports_input_types(self):
        """MalwareBazaar supports URL and DOMAIN."""
        from src.adapters.scanners.malwarebazaar_scanner import MalwareBazaarScanner

        scanner = MalwareBazaarScanner()
        assert scanner.supports(ScanInputType.URL)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP error returns FAILED status."""
        from src.adapters.scanners.malwarebazaar_scanner import MalwareBazaarScanner

        scanner = MalwareBazaarScanner()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("API unavailable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("a" * 64, ScanInputType.URL)

        assert result.status == ScanStatus.FAILED


# ---------------------------------------------------------------------------
# CIRLHashlookupScanner
# ---------------------------------------------------------------------------

class TestCIRLHashlookupScanner:
    """Tests for the CIRCL hash-lookup scanner (known-good database)."""

    async def test_scan_known_good_hash(self):
        """Hash in CIRCL database returns is_known=True, is_malicious=False."""
        from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner

        scanner = CIRLHashlookupScanner()
        sha256 = "a" * 64

        mock = _mock_httpx({
            "SHA-256": sha256,
            "FileName": "notepad.exe",
            "FileSize": "67584",
            "CRC32": "AABBCCDD",
            "MD5": "b" * 32,
            "SHA-1": "c" * 40,
            "SHA-512": "d" * 128,
            "source": "NSRL",
            "ProductName": "Microsoft Windows",
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan(sha256, ScanInputType.URL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["is_known"] is True
        assert result.raw_data["file_info"]["file_name"] == "notepad.exe"

    async def test_scan_unknown_hash_404(self):
        """404 response marks hash as unknown/potentially malicious."""
        from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner

        scanner = CIRLHashlookupScanner()
        sha1 = "e" * 40  # valid SHA1 length

        mock = _mock_httpx({}, status_code=404)

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan(sha1, ScanInputType.URL)

        assert result.raw_data["found"] is False
        assert result.raw_data["is_known"] is False
        assert result.raw_data["is_malicious"] is True

    async def test_scan_invalid_input(self):
        """Non-hash input returns found=False without network request."""
        from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner

        scanner = CIRLHashlookupScanner()

        result = await scanner.scan("not-a-hash-value", ScanInputType.URL)

        assert result.raw_data["found"] is False
        assert result.raw_data["is_known"] is False
        assert "error" in result.raw_data

    async def test_supports_input_types(self):
        """CIRCL hashlookup uses URL as proxy for hash values."""
        from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner

        scanner = CIRLHashlookupScanner()
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP error returns FAILED status."""
        from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner

        scanner = CIRLHashlookupScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("CIRCL API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        sha256 = "a" * 64

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan(sha256, ScanInputType.URL)

        assert result.status == ScanStatus.FAILED

    async def test_extracts_identifiers_empty(self):
        """Hash lookups produce no pivot identifiers."""
        from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner

        scanner = CIRLHashlookupScanner()
        sha256 = "b" * 64

        mock = _mock_httpx({
            "SHA-256": sha256,
            "FileName": "setup.exe",
            "FileSize": "1024",
            "source": "NSRL",
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan(sha256, ScanInputType.URL)

        assert result.extracted_identifiers == []


# ---------------------------------------------------------------------------
# OpenCorporatesScanner
# ---------------------------------------------------------------------------

class TestOpenCorporatesScanner:
    """Tests for the OpenCorporates corporate registry scanner."""

    async def test_scan_domain_company_found(self):
        """Domain input searches companies and returns results."""
        from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner

        scanner = OpenCorporatesScanner()

        mock = _mock_httpx({
            "results": {
                "companies": [
                    {
                        "company": {
                            "name": "Example Corp Ltd",
                            "company_number": "12345678",
                            "jurisdiction_code": "gb",
                            "current_status": "Active",
                            "incorporation_date": "2010-01-01",
                            "registered_address_in_full": "1 Example Street, London",
                            "officers": [
                                {"officer": {"name": "John Smith"}},
                            ],
                        }
                    }
                ]
            }
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("example.co.uk", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert len(result.raw_data["companies"]) == 1
        assert result.raw_data["companies"][0]["name"] == "Example Corp Ltd"

    async def test_scan_domain_not_found(self):
        """Empty results returns found=False."""
        from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner

        scanner = OpenCorporatesScanner()

        mock = _mock_httpx({"results": {"companies": []}})

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("nonexistent-xyz.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_scan_username_officer_search(self):
        """USERNAME input searches officers."""
        from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner

        scanner = OpenCorporatesScanner()

        mock = _mock_httpx({
            "results": {
                "officers": [
                    {
                        "officer": {
                            "name": "Jane Smith",
                            "position": "Director",
                            "start_date": "2015-03-01",
                            "end_date": None,
                            "company": {"name": "Tech Corp", "jurisdiction_code": "us_de"},
                        }
                    }
                ]
            }
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("Jane Smith", ScanInputType.USERNAME)

        assert result.raw_data["found"] is True
        assert len(result.raw_data["officers"]) == 1

    async def test_supports_input_types(self):
        """OpenCorporates supports DOMAIN and USERNAME."""
        from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner

        scanner = OpenCorporatesScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP 500 returns FAILED status."""
        from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner

        scanner = OpenCorporatesScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("API error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.FAILED

    async def test_extracts_officer_identifiers(self):
        """Officer names extracted as person: identifiers."""
        from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner

        scanner = OpenCorporatesScanner()

        mock = _mock_httpx({
            "results": {
                "companies": [
                    {
                        "company": {
                            "name": "Acme Ltd",
                            "company_number": "999",
                            "jurisdiction_code": "gb",
                            "current_status": "Active",
                            "incorporation_date": "",
                            "registered_address_in_full": "",
                            "officers": [
                                {"officer": {"name": "Alice Johnson"}},
                                {"officer": {"name": "Bob Williams"}},
                            ],
                        }
                    }
                ]
            }
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("acme.co.uk", ScanInputType.DOMAIN)

        assert "person:Alice Johnson" in result.extracted_identifiers
        assert "person:Bob Williams" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# SECEdgarScanner
# ---------------------------------------------------------------------------

class TestSECEdgarScanner:
    """Tests for the SEC EDGAR company filings scanner."""

    async def test_scan_company_found(self):
        """Company found in EDGAR returns filings and executives."""
        from src.adapters.scanners.secedgar_scanner import SECEdgarScanner

        scanner = SECEdgarScanner()

        search_resp = _mock_resp(
            status_code=200,
            text=(
                "CIK=1234567&company=APPLE INC"
                "<company-name>Apple Inc</company-name>"
                "<assigned-sic-desc>Electronic Computers</assigned-sic-desc>"
                "<state-of-incorporation>CA</state-of-incorporation>"
            ),
        )

        submissions_resp = _mock_resp({
            "filings": {
                "recent": {
                    "form": ["10-K", "8-K"],
                    "filingDate": ["2024-01-01", "2024-02-01"],
                    "primaryDocument": ["form10k.htm", "form8k.htm"],
                    "accessionNumber": ["0001234-24-000001", "0001234-24-000002"],
                }
            },
            "officers": [
                {"name": "Tim Cook"},
                {"name": "Luca Maestri"},
            ],
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[search_resp, submissions_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("apple.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["company_name"] == "Apple Inc"

    async def test_scan_company_not_found(self):
        """Empty EDGAR response returns found=False."""
        from src.adapters.scanners.secedgar_scanner import SECEdgarScanner

        scanner = SECEdgarScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_resp(status_code=200, text="no results here"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistentcompany-xyz.io", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """SEC EDGAR supports DOMAIN and USERNAME."""
        from src.adapters.scanners.secedgar_scanner import SECEdgarScanner

        scanner = SECEdgarScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """HTTP error is handled gracefully — found=False, no raise."""
        from src.adapters.scanners.secedgar_scanner import SECEdgarScanner

        scanner = SECEdgarScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("EDGAR down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("apple.com", ScanInputType.DOMAIN)

        assert result.raw_data.get("found") is False

    async def test_extracts_person_and_url_identifiers(self):
        """Executive names and filing URLs extracted as identifiers."""
        from src.adapters.scanners.secedgar_scanner import SECEdgarScanner

        scanner = SECEdgarScanner()

        search_resp = _mock_resp(
            status_code=200,
            text="CIK=0000050863 <company-name>Test Corp</company-name>",
        )

        submissions_resp = _mock_resp({
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": ["2024-01-01"],
                    "primaryDocument": ["form.htm"],
                    "accessionNumber": ["0000050863-24-000001"],
                }
            },
            "officers": [{"name": "Jane CEO"}],
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[search_resp, submissions_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testcorp.com", ScanInputType.DOMAIN)

        assert "person:Jane CEO" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# OpenSanctionsScanner
# ---------------------------------------------------------------------------

class TestOpenSanctionsScanner:
    """Tests for the OpenSanctions sanctions/PEP list scanner."""

    async def test_scan_sanctioned_entity_found(self):
        """Sanctioned entity returns is_sanctioned=True."""
        from src.adapters.scanners.opensanctions_scanner import OpenSanctionsScanner

        scanner = OpenSanctionsScanner()

        mock = _mock_httpx({
            "results": [
                {
                    "caption": "Evildoer Corp",
                    "schema": "Organization",
                    "datasets": ["ofac_sdn", "us_ofac_sdn"],
                    "properties": {
                        "alias": ["EvilCo"],
                        "country": ["RU"],
                        "program": ["SDN"],
                        "birthDate": [],
                    },
                    "score": 0.95,
                }
            ]
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("evildoer.ru", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["is_sanctioned"] is True

    async def test_scan_no_matches(self):
        """Empty results returns found=False."""
        from src.adapters.scanners.opensanctions_scanner import OpenSanctionsScanner

        scanner = OpenSanctionsScanner()

        mock = _mock_httpx({"results": []})

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("clean.example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert result.raw_data["is_sanctioned"] is False

    async def test_supports_input_types(self):
        """OpenSanctions supports DOMAIN, USERNAME, and EMAIL."""
        from src.adapters.scanners.opensanctions_scanner import OpenSanctionsScanner

        scanner = OpenSanctionsScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.USERNAME)
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP 500 error is handled gracefully — found=False, no raise."""
        from src.adapters.scanners.opensanctions_scanner import OpenSanctionsScanner

        scanner = OpenSanctionsScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data.get("found") is False

    async def test_scan_pep_detection(self):
        """PEP entity in pep dataset returns is_pep=True."""
        from src.adapters.scanners.opensanctions_scanner import OpenSanctionsScanner

        scanner = OpenSanctionsScanner()

        mock = _mock_httpx({
            "results": [
                {
                    "caption": "John Politician",
                    "schema": "Person",
                    "datasets": ["pep_us", "us_politicians"],
                    "properties": {
                        "birthDate": ["1965-03-10"],
                        "country": ["US"],
                        "alias": [],
                        "program": [],
                    },
                    "score": 0.82,
                }
            ]
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("john.politician", ScanInputType.USERNAME)

        assert result.raw_data["is_pep"] is True


# ---------------------------------------------------------------------------
# GDELTScanner
# ---------------------------------------------------------------------------

class TestGDELTScanner:
    """Tests for the GDELT news event scanner."""

    async def test_scan_domain_articles_found(self):
        """GDELT returns news articles mentioning the entity."""
        from src.adapters.scanners.gdelt_scanner import GDELTScanner

        scanner = GDELTScanner()

        articles_resp = _mock_resp({
            "articles": [
                {
                    "url": "https://news.example.com/story1",
                    "title": "Breaking: Example Corp in the news",
                    "seendate": "20240115T120000Z",
                    "domain": "news.example.com",
                    "language": "English",
                    "sourcecountry": "US",
                    "socialimage": "",
                },
                {
                    "url": "https://reporter.example.org/story2",
                    "title": "Follow-up on Example Corp",
                    "seendate": "20240116T080000Z",
                    "domain": "reporter.example.org",
                    "language": "English",
                    "sourcecountry": "GB",
                    "socialimage": "",
                },
            ]
        })

        timeline_resp = _mock_resp({
            "timeline": [
                {"data": [{"date": "2024-01-15", "value": 0.5}]}
            ]
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[articles_resp, timeline_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["total_articles"] == 2

    async def test_scan_no_articles(self):
        """Empty article list returns found=False."""
        from src.adapters.scanners.gdelt_scanner import GDELTScanner

        scanner = GDELTScanner()

        empty_resp = _mock_resp({"articles": []})
        timeline_resp = _mock_resp({"timeline": []})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[empty_resp, timeline_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("unknownterm-xyz.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert result.raw_data["total_articles"] == 0

    async def test_supports_input_types(self):
        """GDELT supports DOMAIN and USERNAME."""
        from src.adapters.scanners.gdelt_scanner import GDELTScanner

        scanner = GDELTScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP error is handled gracefully — found=False, no raise."""
        from src.adapters.scanners.gdelt_scanner import GDELTScanner

        scanner = GDELTScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("GDELT down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data.get("found") is False

    async def test_extracts_article_url_identifiers(self):
        """First 5 article URLs extracted as url: identifiers."""
        from src.adapters.scanners.gdelt_scanner import GDELTScanner

        scanner = GDELTScanner()

        articles_resp = _mock_resp({
            "articles": [
                {
                    "url": "https://news.example.com/story1",
                    "title": "Story 1",
                    "seendate": "20240101",
                    "domain": "news.example.com",
                    "language": "English",
                    "sourcecountry": "US",
                },
            ]
        })

        timeline_resp = _mock_resp({"timeline": []})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[articles_resp, timeline_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "url:https://news.example.com/story1" in result.extracted_identifiers
