"""Unit tests for network-focused OSINT scanners.

Covers: InternetDBScanner, HackerTargetScanner, URLScanScanner, ViewDNSScanner,
IPAPIScanner, IPInfoScanner, DNSDumpsterScanner, RIPEStatScanner, WAFDetectScanner.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.entities.types import ScanInputType, ScanStatus


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_httpx(response_data=None, status_code=200, text=None):
    """Create a mock httpx.AsyncClient context manager."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_data if response_data is not None else {}
    mock_resp.text = text if text is not None else str(response_data)
    mock_resp.url = "https://example.com"
    mock_resp.headers = MagicMock()
    mock_resp.headers.get = MagicMock(return_value="")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_httpx_status_error(status_code=500):
    """Create a mock that raises HTTPStatusError."""
    import httpx
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    mock_client = AsyncMock()
    error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_resp)
    mock_client.get = AsyncMock(side_effect=error)
    mock_client.post = AsyncMock(side_effect=error)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# InternetDBScanner
# ---------------------------------------------------------------------------

class TestInternetDBScanner:
    """Tests for the InternetDB (Shodan free) scanner."""

    async def test_scan_success(self):
        """Happy path: IP found with ports, hostnames, and vulns."""
        from src.adapters.scanners.internetdb_scanner import InternetDBScanner

        scanner = InternetDBScanner()
        mock = _mock_httpx({
            "ip": "1.2.3.4",
            "ports": [22, 80, 443],
            "cpes": ["cpe:/a:apache:http_server:2.4"],
            "hostnames": ["server.example.com"],
            "tags": ["self-signed"],
            "vulns": ["CVE-2021-41773"],
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["open_ports"] == [22, 80, 443]
        assert "server.example.com" in result.raw_data["hostnames"]
        assert "CVE-2021-41773" in result.raw_data["vulns"]

    async def test_scan_not_found(self):
        """404 response returns found=False."""
        from src.adapters.scanners.internetdb_scanner import InternetDBScanner

        scanner = InternetDBScanner()
        mock = _mock_httpx({}, status_code=404)

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("192.0.2.1", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """InternetDB scanner only supports IP_ADDRESS."""
        from src.adapters.scanners.internetdb_scanner import InternetDBScanner

        scanner = InternetDBScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """HTTP error returns found=False with error key."""
        from src.adapters.scanners.internetdb_scanner import InternetDBScanner

        scanner = InternetDBScanner()
        mock = _mock_httpx_status_error(500)

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False
        assert "error" in result.raw_data

    async def test_extracts_identifiers(self):
        """Hostnames and CVEs are extracted as identifiers."""
        from src.adapters.scanners.internetdb_scanner import InternetDBScanner

        scanner = InternetDBScanner()
        mock = _mock_httpx({
            "ip": "1.2.3.4",
            "ports": [443],
            "cpes": [],
            "hostnames": ["host.example.com"],
            "tags": [],
            "vulns": ["CVE-2023-1234"],
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert "domain:host.example.com" in result.extracted_identifiers
        assert "vuln:CVE-2023-1234" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# HackerTargetScanner
# ---------------------------------------------------------------------------

class TestHackerTargetScanner:
    """Tests for the HackerTarget free DNS/subdomain scanner."""

    async def test_scan_domain_success(self):
        """Domain scan returns subdomains and DNS records."""
        from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner

        scanner = HackerTargetScanner()

        hostsearch_resp = MagicMock()
        hostsearch_resp.status_code = 200
        hostsearch_resp.raise_for_status = MagicMock()
        hostsearch_resp.text = "api.example.com,1.2.3.4\nmail.example.com,5.6.7.8\n"

        dns_resp = MagicMock()
        dns_resp.status_code = 200
        dns_resp.raise_for_status = MagicMock()
        dns_resp.text = "example.com. IN A 1.2.3.4\nexample.com. IN MX mail.example.com\n"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[hostsearch_resp, dns_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert len(result.raw_data["subdomains"]) == 2

    async def test_scan_ip_success(self):
        """IP reverse lookup returns co-hosted domains."""
        from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner

        scanner = HackerTargetScanner()
        mock = _mock_httpx(text="example.com\nother.com\n")

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert "example.com" in result.raw_data["co_hosted_domains"]

    async def test_scan_not_found(self):
        """Error text from hackertarget returns found=False."""
        from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner

        scanner = HackerTargetScanner()

        error_resp = MagicMock()
        error_resp.status_code = 200
        error_resp.raise_for_status = MagicMock()
        error_resp.text = "error check your search parameter"

        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.raise_for_status = MagicMock()
        empty_resp.text = ""

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[error_resp, empty_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent.xyz", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """HackerTarget supports DOMAIN and IP_ADDRESS."""
        from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner

        scanner = HackerTargetScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """Network exception returns found=False."""
        from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner

        scanner = HackerTargetScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers(self):
        """IP and domain identifiers extracted from hostsearch."""
        from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner

        scanner = HackerTargetScanner()

        hostsearch_resp = MagicMock()
        hostsearch_resp.status_code = 200
        hostsearch_resp.raise_for_status = MagicMock()
        hostsearch_resp.text = "api.example.com,10.0.0.1\n"

        dns_resp = MagicMock()
        dns_resp.status_code = 200
        dns_resp.raise_for_status = MagicMock()
        dns_resp.text = ""

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[hostsearch_resp, dns_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "domain:api.example.com" in result.extracted_identifiers
        assert "ip:10.0.0.1" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# URLScanScanner
# ---------------------------------------------------------------------------

class TestURLScanScanner:
    """Tests for the URLScan.io scanner."""

    async def test_scan_domain_success(self):
        """Domain scan returns historical scan results."""
        from src.adapters.scanners.urlscan_scanner import URLScanScanner

        scanner = URLScanScanner()
        mock = _mock_httpx({
            "total": 2,
            "results": [
                {
                    "page": {"ip": "1.2.3.4", "url": "https://example.com/", "country": "US",
                              "server": "nginx", "title": "Example", "domain": "example.com"},
                    "verdicts": {"overall": {"malicious": False}},
                    "task": {"uuid": "abc123", "time": "2024-01-01"},
                },
            ],
        })

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.urlscan_scanner.get_settings") as ms:
                ms.return_value.urlscan_api_key = ""
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["total_results"] == 2

    async def test_scan_not_found(self):
        """Empty results returns found=False."""
        from src.adapters.scanners.urlscan_scanner import URLScanScanner

        scanner = URLScanScanner()
        mock = _mock_httpx({"total": 0, "results": []})

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.urlscan_scanner.get_settings") as ms:
                ms.return_value.urlscan_api_key = ""
                result = await scanner.scan("nonexistent.xyz", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """URLScan supports DOMAIN and URL."""
        from src.adapters.scanners.urlscan_scanner import URLScanScanner

        scanner = URLScanScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP error returns found=False."""
        from src.adapters.scanners.urlscan_scanner import URLScanScanner

        scanner = URLScanScanner()
        mock = _mock_httpx_status_error(429)

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.urlscan_scanner.get_settings") as ms:
                ms.return_value.urlscan_api_key = ""
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert "error" in result.raw_data

    async def test_extracts_identifiers(self):
        """IPs and URLs extracted from scan results."""
        from src.adapters.scanners.urlscan_scanner import URLScanScanner

        scanner = URLScanScanner()
        mock = _mock_httpx({
            "total": 1,
            "results": [
                {
                    "page": {"ip": "9.9.9.9", "url": "https://example.com/page",
                              "country": "US", "server": "", "title": "", "domain": "example.com"},
                    "verdicts": {"overall": {"malicious": False}},
                    "task": {"uuid": "xyz", "time": "2024-01-01"},
                },
            ],
        })

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.urlscan_scanner.get_settings") as ms:
                ms.return_value.urlscan_api_key = ""
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "ip:9.9.9.9" in result.extracted_identifiers
        assert "url:https://example.com/page" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# ViewDNSScanner
# ---------------------------------------------------------------------------

class TestViewDNSScanner:
    """Tests for the ViewDNS.info scanner."""

    async def test_scan_domain_ip_history(self):
        """Domain scan returns historical IPs."""
        from src.adapters.scanners.viewdns_scanner import ViewDNSScanner

        scanner = ViewDNSScanner()
        mock = _mock_httpx({
            "response": {
                "records": [
                    {"ip": "1.2.3.4", "location": "US", "owner": "Acme", "lastseen": "2024-01-01"},
                ]
            }
        })

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.viewdns_scanner.get_settings") as ms:
                ms.return_value.viewdns_api_key = "testkey"
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert len(result.raw_data["ip_history"]) == 1

    async def test_scan_no_api_key(self):
        """Without API key returns found=False with error message."""
        from src.adapters.scanners.viewdns_scanner import ViewDNSScanner

        scanner = ViewDNSScanner()

        with patch("src.adapters.scanners.viewdns_scanner.get_settings") as ms:
            ms.return_value.viewdns_api_key = ""
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert "error" in result.raw_data

    async def test_supports_input_types(self):
        """ViewDNS supports DOMAIN, IP_ADDRESS, and EMAIL."""
        from src.adapters.scanners.viewdns_scanner import ViewDNSScanner

        scanner = ViewDNSScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.USERNAME)

    async def test_handles_http_error(self):
        """HTTP error returns found=False."""
        from src.adapters.scanners.viewdns_scanner import ViewDNSScanner

        scanner = ViewDNSScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.viewdns_scanner.get_settings") as ms:
                ms.return_value.viewdns_api_key = "testkey"
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers_from_ip_history(self):
        """IPs from history are extracted as ip: identifiers."""
        from src.adapters.scanners.viewdns_scanner import ViewDNSScanner

        scanner = ViewDNSScanner()
        mock = _mock_httpx({
            "response": {
                "records": [
                    {"ip": "192.168.1.1", "location": "", "owner": "", "lastseen": ""},
                ]
            }
        })

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.viewdns_scanner.get_settings") as ms:
                ms.return_value.viewdns_api_key = "testkey"
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "ip:192.168.1.1" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# IPAPIScanner
# ---------------------------------------------------------------------------

class TestIPAPIScanner:
    """Tests for the ip-api.com geolocation scanner."""

    async def test_scan_success(self):
        """Happy path returns geolocation data."""
        from src.adapters.scanners.ipapi_scanner import IPAPIScanner

        scanner = IPAPIScanner()
        mock = _mock_httpx({
            "status": "success",
            "query": "8.8.8.8",
            "continent": "North America",
            "country": "United States",
            "countryCode": "US",
            "region": "VA",
            "regionName": "Virginia",
            "city": "Ashburn",
            "zip": "20149",
            "lat": 39.03,
            "lon": -77.5,
            "timezone": "America/New_York",
            "isp": "Google LLC",
            "org": "Google Public DNS",
            "as": "AS15169 Google LLC",
            "asname": "GOOGLE",
            "mobile": False,
            "proxy": False,
            "hosting": True,
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["country"] == "United States"
        assert result.raw_data["isp"] == "Google LLC"

    async def test_scan_not_found(self):
        """ip-api failure status returns found=False."""
        from src.adapters.scanners.ipapi_scanner import IPAPIScanner

        scanner = IPAPIScanner()
        mock = _mock_httpx({"status": "fail", "message": "private range", "query": "192.168.1.1"})

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("192.168.1.1", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """IPAPI supports only IP_ADDRESS."""
        from src.adapters.scanners.ipapi_scanner import IPAPIScanner

        scanner = IPAPIScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_handles_http_error(self):
        """HTTP error returns found=False."""
        from src.adapters.scanners.ipapi_scanner import IPAPIScanner

        scanner = IPAPIScanner()
        mock = _mock_httpx_status_error(503)

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers_empty(self):
        """IPAPI is enrichment only — no pivot identifiers."""
        from src.adapters.scanners.ipapi_scanner import IPAPIScanner

        scanner = IPAPIScanner()
        mock = _mock_httpx({
            "status": "success", "query": "8.8.8.8",
            "country": "US", "isp": "Google LLC",
        })

        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.extracted_identifiers == []


# ---------------------------------------------------------------------------
# IPInfoScanner
# ---------------------------------------------------------------------------

class TestIPInfoScanner:
    """Tests for the IPInfo.io scanner."""

    async def test_scan_success(self):
        """Happy path returns hostname and location data."""
        from src.adapters.scanners.ipinfo_scanner import IPInfoScanner

        scanner = IPInfoScanner()
        mock = _mock_httpx({
            "ip": "8.8.8.8",
            "hostname": "dns.google",
            "city": "Mountain View",
            "region": "California",
            "country": "US",
            "loc": "37.3861,-122.0839",
            "org": "AS15169 Google LLC",
            "postal": "94035",
            "timezone": "America/Los_Angeles",
        })

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.ipinfo_scanner.get_settings") as ms:
                ms.return_value.ipinfo_api_key = ""
                result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["hostname"] == "dns.google"

    async def test_scan_bogon_ip(self):
        """Bogon/reserved IP returns found=False."""
        from src.adapters.scanners.ipinfo_scanner import IPInfoScanner

        scanner = IPInfoScanner()
        mock = _mock_httpx({"ip": "192.168.0.1", "bogon": True})

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.ipinfo_scanner.get_settings") as ms:
                ms.return_value.ipinfo_api_key = ""
                result = await scanner.scan("192.168.0.1", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False
        assert result.raw_data.get("bogon") is True

    async def test_supports_input_types(self):
        """IPInfo supports only IP_ADDRESS."""
        from src.adapters.scanners.ipinfo_scanner import IPInfoScanner

        scanner = IPInfoScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """HTTP error returns found=False."""
        from src.adapters.scanners.ipinfo_scanner import IPInfoScanner

        scanner = IPInfoScanner()
        mock = _mock_httpx_status_error(429)

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.ipinfo_scanner.get_settings") as ms:
                ms.return_value.ipinfo_api_key = ""
                result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False

    async def test_extracts_hostname_identifier(self):
        """Hostname is extracted as domain: identifier."""
        from src.adapters.scanners.ipinfo_scanner import IPInfoScanner

        scanner = IPInfoScanner()
        mock = _mock_httpx({
            "ip": "8.8.8.8",
            "hostname": "dns.google",
            "city": "Mountain View",
            "country": "US",
            "loc": "37.0,-122.0",
            "org": "AS15169 Google LLC",
        })

        with patch("httpx.AsyncClient", return_value=mock):
            with patch("src.adapters.scanners.ipinfo_scanner.get_settings") as ms:
                ms.return_value.ipinfo_api_key = ""
                result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert "domain:dns.google" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# DNSDumpsterScanner
# ---------------------------------------------------------------------------

class TestDNSDumpsterScanner:
    """Tests for the DNSDumpster HTML-scraping scanner."""

    async def test_scan_success(self):
        """Happy path: CSRF token found, POST returns HTML with subdomains."""
        from src.adapters.scanners.dnsdumpster_scanner import DNSDumpsterScanner

        scanner = DNSDumpsterScanner()

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.raise_for_status = MagicMock()
        get_resp.text = '<input name="csrfmiddlewaretoken" value="testtoken123">'

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.raise_for_status = MagicMock()
        post_resp.text = (
            "<h4>A Records</h4><table>"
            "<tr><td>api.example.com</td><td>1.2.3.4</td></tr>"
            "</table>"
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.post = AsyncMock(return_value=post_resp)
        mock_client.cookies = MagicMock()
        mock_client.cookies.get = MagicMock(return_value="testtoken123")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS

    async def test_scan_no_csrf_token(self):
        """When CSRF token cannot be obtained, returns found=False."""
        from src.adapters.scanners.dnsdumpster_scanner import DNSDumpsterScanner

        scanner = DNSDumpsterScanner()

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.raise_for_status = MagicMock()
        get_resp.text = "<html><body>No token here</body></html>"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.post = AsyncMock(return_value=MagicMock())
        mock_client.cookies = MagicMock()
        mock_client.cookies.get = MagicMock(return_value="")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """DNSDumpster supports only DOMAIN."""
        from src.adapters.scanners.dnsdumpster_scanner import DNSDumpsterScanner

        scanner = DNSDumpsterScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_exception(self):
        """Network exception returns found=False."""
        from src.adapters.scanners.dnsdumpster_scanner import DNSDumpsterScanner

        scanner = DNSDumpsterScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert "error" in result.raw_data

    async def test_extracts_identifiers(self):
        """Subdomain and IP identifiers extracted from A records table."""
        from src.adapters.scanners.dnsdumpster_scanner import DNSDumpsterScanner

        scanner = DNSDumpsterScanner()

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.raise_for_status = MagicMock()
        get_resp.text = ""

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.raise_for_status = MagicMock()
        post_resp.text = (
            "<h4>A Records</h4><table>"
            "<tr><td>sub.example.com</td><td>10.0.0.5</td></tr>"
            "</table>"
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=get_resp)
        mock_client.post = AsyncMock(return_value=post_resp)
        mock_client.cookies = MagicMock()
        mock_client.cookies.get = MagicMock(return_value="csrf_abc")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        identifiers = result.raw_data.get("extracted_identifiers", [])
        assert "domain:sub.example.com" in identifiers
        assert "ip:10.0.0.5" in identifiers


# ---------------------------------------------------------------------------
# RIPEStatScanner
# ---------------------------------------------------------------------------

class TestRIPEStatScanner:
    """Tests for the RIPEstat BGP/ASN scanner."""

    async def test_scan_ip_success(self):
        """Happy path returns ASN, prefix, and abuse contact."""
        from src.adapters.scanners.ripestat_scanner import RIPEStatScanner

        scanner = RIPEStatScanner()

        prefix_resp = MagicMock()
        prefix_resp.status_code = 200
        prefix_resp.raise_for_status = MagicMock()
        prefix_resp.json.return_value = {
            "data": {
                "asns": [{"asn": 15169, "holder": "Google LLC"}],
                "resource": "8.8.8.0/24",
                "block": {"desc": "US"},
            }
        }

        abuse_resp = MagicMock()
        abuse_resp.status_code = 200
        abuse_resp.raise_for_status = MagicMock()
        abuse_resp.json.return_value = {
            "data": {"abuse_contacts": ["abuse@google.com"]}
        }

        routing_resp = MagicMock()
        routing_resp.status_code = 200
        routing_resp.raise_for_status = MagicMock()
        routing_resp.json.return_value = {"data": {"by_origin": []}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[prefix_resp, abuse_resp, routing_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["asn"] == 15169

    async def test_scan_not_found(self):
        """Empty asns list returns found=False."""
        from src.adapters.scanners.ripestat_scanner import RIPEStatScanner

        scanner = RIPEStatScanner()

        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.raise_for_status = MagicMock()
        empty_resp.json.return_value = {"data": {"asns": [], "resource": "", "block": {}}}

        no_abuse = MagicMock()
        no_abuse.status_code = 200
        no_abuse.raise_for_status = MagicMock()
        no_abuse.json.return_value = {"data": {"abuse_contacts": []}}

        no_routing = MagicMock()
        no_routing.status_code = 200
        no_routing.raise_for_status = MagicMock()
        no_routing.json.return_value = {"data": {"by_origin": []}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[empty_resp, no_abuse, no_routing])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("192.0.2.1", ScanInputType.IP_ADDRESS)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """RIPEstat supports IP_ADDRESS and DOMAIN."""
        from src.adapters.scanners.ripestat_scanner import RIPEStatScanner

        scanner = RIPEStatScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_error(self):
        """Exception during requests returns found=False gracefully."""
        from src.adapters.scanners.ripestat_scanner import RIPEStatScanner

        scanner = RIPEStatScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        # RIPEstat uses return_exceptions=True in gather, so errors are handled
        # gracefully without raising — status is SUCCESS but found is False
        assert result.raw_data.get("found") is False

    async def test_extracts_identifiers(self):
        """ASN and abuse email extracted as identifiers."""
        from src.adapters.scanners.ripestat_scanner import RIPEStatScanner

        scanner = RIPEStatScanner()

        prefix_resp = MagicMock()
        prefix_resp.status_code = 200
        prefix_resp.raise_for_status = MagicMock()
        prefix_resp.json.return_value = {
            "data": {
                "asns": [{"asn": 1234, "holder": "TestOrg"}],
                "resource": "1.2.3.0/24",
                "block": {"desc": "DE"},
            }
        }

        abuse_resp = MagicMock()
        abuse_resp.status_code = 200
        abuse_resp.raise_for_status = MagicMock()
        abuse_resp.json.return_value = {
            "data": {"abuse_contacts": ["abuse@testorg.example"]}
        }

        routing_resp = MagicMock()
        routing_resp.status_code = 200
        routing_resp.raise_for_status = MagicMock()
        routing_resp.json.return_value = {"data": {"by_origin": []}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[prefix_resp, abuse_resp, routing_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert "asn:1234" in result.extracted_identifiers
        assert "email:abuse@testorg.example" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# WAFDetectScanner
# ---------------------------------------------------------------------------

class TestWAFDetectScanner:
    """Tests for the WAF fingerprinting scanner."""

    def _make_waf_response(self, headers_dict=None, body="", status_code=200):
        import httpx
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = status_code
        mock_resp.text = body
        mock_resp.headers = httpx.Headers(headers_dict or {})
        return mock_resp

    async def test_scan_cloudflare_detected(self):
        """Cloudflare WAF detected via CF-Ray header."""
        from src.adapters.scanners.waf_scanner import WAFDetectScanner

        scanner = WAFDetectScanner()
        cf_resp = self._make_waf_response({"CF-Ray": "abc123-LHR", "Server": "cloudflare"})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=cf_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["waf_detected"] is True
        assert result.raw_data["waf_vendor"] == "Cloudflare"

    async def test_scan_no_waf(self):
        """No WAF signatures in response returns waf_detected=False."""
        from src.adapters.scanners.waf_scanner import WAFDetectScanner

        scanner = WAFDetectScanner()
        plain_resp = self._make_waf_response({"Server": "apache"}, body="<html>Hello</html>")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=plain_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["waf_detected"] is False

    async def test_supports_input_types(self):
        """WAFDetect supports DOMAIN and URL."""
        from src.adapters.scanners.waf_scanner import WAFDetectScanner

        scanner = WAFDetectScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """Exception during probing returns found=False."""
        from src.adapters.scanners.waf_scanner import WAFDetectScanner

        scanner = WAFDetectScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers_empty(self):
        """WAF detection is enrichment only — no pivot identifiers."""
        from src.adapters.scanners.waf_scanner import WAFDetectScanner

        scanner = WAFDetectScanner()
        cf_resp = self._make_waf_response({"CF-Ray": "abc-LHR"})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=cf_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.extracted_identifiers == []
