"""Unit tests for subdomain enumeration and web probing scanners.

Covers: Sublist3rScanner (fallback APIs), AmassScanner (fallback),
SubfinderScanner (fallback), DnsxScanner, WaybackCdxScanner,
HttpxProbeScanner, TheHarvesterScanner (fallback).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.core.domain.entities.types import ScanInputType, ScanStatus


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_resp(response_data=None, status_code=200, text=None):
    """Build a minimal mock httpx response."""
    mock_r = MagicMock()
    mock_r.status_code = status_code
    mock_r.raise_for_status = MagicMock()
    mock_r.json.return_value = response_data if response_data is not None else {}
    mock_r.text = text if text is not None else str(response_data)
    mock_r.url = "https://example.com"
    return mock_r


def _mock_httpx(response_data=None, status_code=200, text=None):
    """Create a simple mock client that always returns the same response."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.post = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_httpx_multi(responses):
    """Create a mock client that returns different responses per call (side_effect)."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.post = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# Sublist3rScanner
# ---------------------------------------------------------------------------

class TestSublist3rScanner:
    """Tests for the Sublist3r scanner (fallback API mode)."""

    async def test_scan_fallback_success(self):
        """Fallback APIs return combined, deduplicated subdomains."""
        from src.adapters.scanners.sublist3r_scanner import Sublist3rScanner

        scanner = Sublist3rScanner()

        crt_resp = _mock_resp([
            {"name_value": "api.example.com"},
            {"name_value": "mail.example.com"},
        ])
        hackertarget_resp = _mock_resp(text="cdn.example.com,1.2.3.4\napi.example.com,5.6.7.8\n")
        wayback_resp = _mock_resp([
            ["original"],
            ["https://staging.example.com/page"],
        ])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[crt_resp, hackertarget_resp, wayback_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # Force fallback by making subprocess raise FileNotFoundError
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert "api.example.com" in result.raw_data["subdomains"]
        assert "mail.example.com" in result.raw_data["subdomains"]
        assert result.raw_data["method"] == "fallback_apis"

    async def test_scan_no_results(self):
        """Empty API responses return found=False."""
        from src.adapters.scanners.sublist3r_scanner import Sublist3rScanner

        scanner = Sublist3rScanner()

        empty_crt = _mock_resp([])
        empty_ht = _mock_resp(text="")
        empty_wb = _mock_resp([["original"]])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[empty_crt, empty_ht, empty_wb])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("nonexistent-xyz.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert result.raw_data["subdomains"] == []

    async def test_supports_input_types(self):
        """Sublist3r only supports DOMAIN."""
        from src.adapters.scanners.sublist3r_scanner import Sublist3rScanner

        scanner = Sublist3rScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_api_error(self):
        """When all fallback sources fail, returns found=False gracefully."""
        from src.adapters.scanners.sublist3r_scanner import Sublist3rScanner

        scanner = Sublist3rScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("All down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers(self):
        """Each discovered subdomain produces a domain: identifier."""
        from src.adapters.scanners.sublist3r_scanner import Sublist3rScanner

        scanner = Sublist3rScanner()

        crt_resp = _mock_resp([{"name_value": "dev.example.com"}])
        ht_resp = _mock_resp(text="")
        wb_resp = _mock_resp([["original"]])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[crt_resp, ht_resp, wb_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "domain:dev.example.com" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# AmassScanner
# ---------------------------------------------------------------------------

class TestAmassScanner:
    """Tests for the Amass scanner (fallback API mode)."""

    async def test_scan_fallback_returns_subdomains(self):
        """Fallback aggregates crt.sh + rapiddns + bufferover."""
        from src.adapters.scanners.amass_scanner import AmassScanner

        scanner = AmassScanner()

        crt_resp = _mock_resp([{"name_value": "ns1.example.com"}])
        rapiddns_resp = _mock_resp(text="<td>ns2.example.com</td>", status_code=200)
        bufferover_resp = _mock_resp({
            "FDNS_A": ["192.168.1.1,ns3.example.com"],
            "RDNS": [],
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[crt_resp, rapiddns_resp, bufferover_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["method"] == "fallback"

    async def test_scan_no_results(self):
        """All empty fallback sources returns found=False."""
        from src.adapters.scanners.amass_scanner import AmassScanner

        scanner = AmassScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            _mock_resp([]),
            _mock_resp(text="<html></html>"),
            _mock_resp({"FDNS_A": [], "RDNS": []}),
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("empty.xyz", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """Amass supports only DOMAIN."""
        from src.adapters.scanners.amass_scanner import AmassScanner

        scanner = AmassScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_network_failure(self):
        """Network failure in fallback returns found=False."""
        from src.adapters.scanners.amass_scanner import AmassScanner

        scanner = AmassScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers(self):
        """Discovered subdomains produce domain: identifiers."""
        from src.adapters.scanners.amass_scanner import AmassScanner

        scanner = AmassScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            _mock_resp([{"name_value": "vpn.example.com"}]),
            _mock_resp(text=""),
            _mock_resp({"FDNS_A": [], "RDNS": []}),
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "domain:vpn.example.com" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# SubfinderScanner
# ---------------------------------------------------------------------------

class TestSubfinderScanner:
    """Tests for the Subfinder scanner (fallback API mode)."""

    async def test_scan_fallback_success(self):
        """Fallback queries anubis, crt.sh, hackertarget, threatcrowd."""
        from src.adapters.scanners.subfinder_scanner import SubfinderScanner

        scanner = SubfinderScanner()

        anubis_resp = _mock_resp(["ftp.example.com", "smtp.example.com"])
        crt_resp = _mock_resp([{"name_value": "www.example.com"}])
        ht_resp = _mock_resp(text="admin.example.com,1.2.3.4\n")
        tc_resp = _mock_resp({"subdomains": ["beta.example.com"]})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[anubis_resp, crt_resp, ht_resp, tc_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["source"] == "fallback_apis"
        assert result.raw_data["found"] is True

    async def test_scan_no_results(self):
        """Empty fallback results return found=False."""
        from src.adapters.scanners.subfinder_scanner import SubfinderScanner

        scanner = SubfinderScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            _mock_resp([]),
            _mock_resp([]),
            _mock_resp(text=""),
            _mock_resp({"subdomains": []}),
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("empty.xyz", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """Subfinder supports only DOMAIN."""
        from src.adapters.scanners.subfinder_scanner import SubfinderScanner

        scanner = SubfinderScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_network_failure(self):
        """Network failure returns empty result."""
        from src.adapters.scanners.subfinder_scanner import SubfinderScanner

        scanner = SubfinderScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers(self):
        """Each subdomain produces a domain: identifier."""
        from src.adapters.scanners.subfinder_scanner import SubfinderScanner

        scanner = SubfinderScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            _mock_resp(["assets.example.com"]),
            _mock_resp([]),
            _mock_resp(text=""),
            _mock_resp({"subdomains": []}),
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "domain:assets.example.com" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# DnsxScanner
# ---------------------------------------------------------------------------

class TestDnsxScanner:
    """Tests for the DNS record resolution scanner (dnspython)."""

    async def test_scan_domain_success(self):
        """DNS records resolved via dnspython mock."""
        from src.adapters.scanners.dnsx_scanner import DnsxScanner

        scanner = DnsxScanner()

        # Mock dns.resolver and dns.reversename
        mock_resolver = MagicMock()

        a_rdata = MagicMock()
        a_rdata.address = "1.2.3.4"

        mx_rdata = MagicMock()
        mx_rdata.preference = 10
        mx_rdata.exchange = MagicMock()
        mx_rdata.exchange.__str__ = lambda self: "mail.example.com."

        ns_rdata = MagicMock()
        ns_rdata.target = MagicMock()
        ns_rdata.target.__str__ = lambda self: "ns1.example.com."

        def mock_resolve(domain, rtype):
            if rtype == "A":
                return [a_rdata]
            if rtype == "MX":
                return [mx_rdata]
            if rtype == "NS":
                return [ns_rdata]
            raise Exception(f"No {rtype} record")

        mock_resolver.resolve = mock_resolve
        mock_resolver.lifetime = 10

        import asyncio

        async def run_executor(executor, func, *args):
            return func()

        with patch("dns.resolver.Resolver", return_value=mock_resolver):
            with patch("dns.reversename.from_address", return_value="4.3.2.1.in-addr.arpa"):
                with patch.object(
                    asyncio.get_event_loop().__class__,
                    "run_in_executor",
                    new=run_executor,
                ):
                    result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS

    async def test_scan_domain_dnspython_not_installed(self):
        """Missing dnspython returns found=False with error."""
        from src.adapters.scanners.dnsx_scanner import DnsxScanner

        scanner = DnsxScanner()

        with patch.dict("sys.modules", {"dns": None, "dns.resolver": None, "dns.reversename": None}):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_scan_ip_ptr(self):
        """IP scan returns PTR records."""
        from src.adapters.scanners.dnsx_scanner import DnsxScanner

        scanner = DnsxScanner()

        ptr_rdata = MagicMock()
        ptr_rdata.target = MagicMock()
        ptr_rdata.target.__str__ = lambda self: "hostname.example.com."

        mock_resolver = MagicMock()
        mock_resolver.resolve = MagicMock(return_value=[ptr_rdata])
        mock_resolver.lifetime = 10

        with patch("dns.resolver.Resolver", return_value=mock_resolver):
            with patch("dns.reversename.from_address", return_value="4.3.2.1.in-addr.arpa"):
                import asyncio

                async def run_executor(executor, func, *args):
                    return func()

                with patch.object(
                    asyncio.get_event_loop().__class__,
                    "run_in_executor",
                    new=run_executor,
                ):
                    result = await scanner.scan("1.2.3.4", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS

    async def test_supports_input_types(self):
        """DnsxScanner supports DOMAIN and IP_ADDRESS."""
        from src.adapters.scanners.dnsx_scanner import DnsxScanner

        scanner = DnsxScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_extracts_ip_and_domain_identifiers(self):
        """Resolved IPs and MX/NS servers are extracted as identifiers."""
        from src.adapters.scanners.dnsx_scanner import DnsxScanner

        scanner = DnsxScanner()

        # The scanner calls run_in_executor to call resolver.resolve
        # We can simulate by making _scan_domain return a known result
        expected = {
            "input": "example.com",
            "found": True,
            "records": {"A": ["1.2.3.4"]},
            "resolved_ips": ["1.2.3.4"],
            "mx_servers": ["mail.example.com"],
            "nameservers": [],
            "txt_records": [],
            "has_dnssec": False,
            "ptr_records": [],
            "extracted_identifiers": ["ip:1.2.3.4", "domain:mail.example.com"],
        }

        with patch.object(scanner, "_scan_domain", AsyncMock(return_value=expected)):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "ip:1.2.3.4" in result.extracted_identifiers
        assert "domain:mail.example.com" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# WaybackCdxScanner
# ---------------------------------------------------------------------------

class TestWaybackCdxScanner:
    """Tests for the Wayback Machine CDX API scanner."""

    async def test_scan_success_with_interesting_urls(self):
        """CDX results include interesting paths and subdomains."""
        from src.adapters.scanners.wayback_cdx_scanner import WaybackCdxScanner

        scanner = WaybackCdxScanner()

        main_cdx_resp = _mock_resp([
            ["original", "statuscode", "timestamp", "mimetype"],
            ["https://example.com/admin/login", "200", "20230101000000", "text/html"],
            ["https://example.com/index.html", "200", "20230102000000", "text/html"],
            ["https://example.com/.env", "200", "20230103000000", "text/plain"],
        ])

        subdomain_cdx_resp = _mock_resp([
            ["original"],
            ["https://api.example.com/v1/"],
            ["https://staging.example.com/"],
        ])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[main_cdx_resp, subdomain_cdx_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert len(result.raw_data["interesting_urls"]) >= 2

    async def test_scan_not_found(self):
        """Empty CDX results return found=False."""
        from src.adapters.scanners.wayback_cdx_scanner import WaybackCdxScanner

        scanner = WaybackCdxScanner()

        empty_main = _mock_resp([["original"]])  # header only
        empty_sub = _mock_resp([["original"]])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[empty_main, empty_sub])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("empty.xyz", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """WaybackCDX supports DOMAIN and URL."""
        from src.adapters.scanners.wayback_cdx_scanner import WaybackCdxScanner

        scanner = WaybackCdxScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """HTTP failure is handled gracefully — found=False, no raise."""
        from src.adapters.scanners.wayback_cdx_scanner import WaybackCdxScanner

        scanner = WaybackCdxScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("CDX API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data.get("found") is False

    async def test_extracts_identifiers(self):
        """Interesting URLs and subdomains produce identifiers."""
        from src.adapters.scanners.wayback_cdx_scanner import WaybackCdxScanner

        scanner = WaybackCdxScanner()

        main_resp = _mock_resp([
            ["original", "statuscode", "timestamp", "mimetype"],
            ["https://example.com/api/login", "200", "20230101", "text/html"],
        ])
        sub_resp = _mock_resp([
            ["original"],
            ["https://dev.example.com/"],
        ])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[main_resp, sub_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        ids = result.extracted_identifiers
        assert any(i.startswith("url:") for i in ids) or any(i.startswith("domain:") for i in ids)


# ---------------------------------------------------------------------------
# HttpxProbeScanner
# ---------------------------------------------------------------------------

class TestHttpxProbeScanner:
    """Tests for the HTTP web server fingerprinting scanner."""

    async def test_scan_success(self):
        """Successful probe returns server info and technologies."""
        from src.adapters.scanners.httpx_probe_scanner import HttpxProbeScanner

        scanner = HttpxProbeScanner()

        import httpx as _httpx
        primary_resp = MagicMock(spec=_httpx.Response)
        primary_resp.status_code = 200
        primary_resp.headers = _httpx.Headers({
            "server": "nginx/1.20",
            "x-powered-by": "PHP/8.1",
        })
        primary_resp.text = "<html><head><title>Example Site</title></head><body>wp-content</body></html>"
        primary_resp.history = []
        primary_resp.url = MagicMock()
        primary_resp.url.__str__ = lambda self: "https://example.com"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=primary_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["title"] == "Example Site"
        assert "WordPress" in result.raw_data["technologies"]

    async def test_scan_host_unreachable(self):
        """When all probes fail, returns found=False."""
        from src.adapters.scanners.httpx_probe_scanner import HttpxProbeScanner

        scanner = HttpxProbeScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("NXDOMAIN"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("doesnotexist.xyz", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """HttpxProbe supports DOMAIN and URL."""
        from src.adapters.scanners.httpx_probe_scanner import HttpxProbeScanner

        scanner = HttpxProbeScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_detects_cloudflare_cdn(self):
        """Cloudflare CDN header detected correctly."""
        from src.adapters.scanners.httpx_probe_scanner import HttpxProbeScanner

        scanner = HttpxProbeScanner()

        import httpx as _httpx
        cf_resp = MagicMock(spec=_httpx.Response)
        cf_resp.status_code = 200
        cf_resp.headers = _httpx.Headers({"CF-Ray": "abc123-LHR"})
        cf_resp.text = "<html></html>"
        cf_resp.history = []
        cf_resp.url = MagicMock()
        cf_resp.url.__str__ = lambda self: "https://example.com"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=cf_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["cdn"] == "Cloudflare"

    async def test_extracts_identifiers_empty(self):
        """HttpxProbe is enrichment only — no pivot identifiers."""
        from src.adapters.scanners.httpx_probe_scanner import HttpxProbeScanner

        scanner = HttpxProbeScanner()

        import httpx as _httpx
        resp = MagicMock(spec=_httpx.Response)
        resp.status_code = 200
        resp.headers = _httpx.Headers({})
        resp.text = "<html></html>"
        resp.history = []
        resp.url = MagicMock()
        resp.url.__str__ = lambda self: "https://example.com"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.extracted_identifiers == []


# ---------------------------------------------------------------------------
# TheHarvesterScanner
# ---------------------------------------------------------------------------

class TestTheHarvesterScanner:
    """Tests for the theHarvester email/host harvesting scanner (fallback mode)."""

    async def test_scan_fallback_success(self):
        """Fallback sources return emails from bing, crt.sh, and github."""
        from src.adapters.scanners.theharvester_scanner import TheHarvesterScanner

        scanner = TheHarvesterScanner()

        bing_resp = _mock_resp(text="Found contact@example.com and info@example.com in search results")
        crt_resp = _mock_resp(text='["contact@example.com"]')
        github_resp = _mock_resp({"items": [], "total_count": 0})
        ddg_resp = _mock_resp(text='<div class="result__snippet">John Doe at Example Corp</div>')

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[bing_resp, crt_resp, github_resp, ddg_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["method"] == "fallback"

    async def test_scan_no_results(self):
        """No emails found returns found=False."""
        from src.adapters.scanners.theharvester_scanner import TheHarvesterScanner

        scanner = TheHarvesterScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            _mock_resp(text="no emails here"),
            _mock_resp(text="[]"),
            _mock_resp({"items": []}),
            _mock_resp(text=""),
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("empty-domain-xyz.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False
        assert result.raw_data["emails"] == []

    async def test_supports_input_types(self):
        """theHarvester supports only DOMAIN."""
        from src.adapters.scanners.theharvester_scanner import TheHarvesterScanner

        scanner = TheHarvesterScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)

    async def test_handles_http_error(self):
        """Network failure in fallback returns empty result."""
        from src.adapters.scanners.theharvester_scanner import TheHarvesterScanner

        scanner = TheHarvesterScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.raw_data["found"] is False

    async def test_extracts_identifiers(self):
        """Found emails produce email: identifiers."""
        from src.adapters.scanners.theharvester_scanner import TheHarvesterScanner

        scanner = TheHarvesterScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[
            _mock_resp(text="security@example.com is listed here"),
            _mock_resp(text=""),
            _mock_resp({"items": []}),
            _mock_resp(text=""),
        ])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert "email:security@example.com" in result.extracted_identifiers
