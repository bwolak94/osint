"""Unit tests for all scanner adapters with mocked HTTP.

Each scanner is tested in isolation -- no real network calls are made.
All httpx.AsyncClient instances are mocked via unittest.mock.patch.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200):
    """Create a mock httpx.AsyncClient context manager.

    Returns a mock that works both as ``httpx.AsyncClient(...)`` and as
    ``async with httpx.AsyncClient(...) as client:``.
    """
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


# ============== Shodan Scanner ==============


class TestShodanScanner:
    """Tests for the Shodan scanner (InternetDB fallback and API key paths)."""

    async def test_internetdb_fallback(self):
        """When no API key is configured, the scanner should use the free InternetDB endpoint."""
        from src.adapters.scanners.shodan_scanner import ShodanScanner

        scanner = ShodanScanner()

        mock_client = _mock_httpx_client({
            "ip": "8.8.8.8",
            "ports": [53, 443],
            "hostnames": ["dns.google"],
            "cpes": [],
            "vulns": [],
            "tags": [],
        })

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.adapters.scanners.shodan_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(shodan_api_key="")
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert "ports" in result.raw_data
        assert 53 in result.raw_data["ports"]
        assert result.raw_data["source"] == "internetdb"

    async def test_supports_ip_and_domain(self):
        """Shodan supports IP_ADDRESS and DOMAIN but not EMAIL."""
        from src.adapters.scanners.shodan_scanner import ShodanScanner

        scanner = ShodanScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_shodan_api_with_key(self):
        """When an API key is set, the scanner should call the full Shodan Host API."""
        from src.adapters.scanners.shodan_scanner import ShodanScanner

        scanner = ShodanScanner()

        mock_client = _mock_httpx_client({
            "ip_str": "8.8.8.8",
            "ports": [53, 443],
            "hostnames": ["dns.google"],
            "vulns": ["CVE-2021-1234"],
            "os": "Linux",
            "isp": "Google LLC",
            "country_name": "United States",
            "data": [{"product": "nginx"}],
        })

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.adapters.scanners.shodan_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(shodan_api_key="test-key")
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["source"] == "shodan_api"
        assert result.raw_data["found"] is True
        assert "nginx" in result.raw_data["services"]


# ============== GeoIP Scanner ==============


class TestGeoIPScanner:
    """Tests for the GeoIP scanner (ip-api.com)."""

    async def test_successful_lookup(self):
        """A successful IP geolocation should return country, city, and identifiers."""
        from src.adapters.scanners.geoip_scanner import GeoIPScanner

        scanner = GeoIPScanner()

        mock_client = _mock_httpx_client({
            "status": "success",
            "country": "United States",
            "city": "Ashburn",
            "regionName": "Virginia",
            "lat": 39.03,
            "lon": -77.5,
            "isp": "Google LLC",
            "as": "AS15169 Google LLC",
            "org": "Google LLC",
            "timezone": "America/New_York",
        })

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("8.8.8.8", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["country"] == "United States"
        assert result.raw_data["city"] == "Ashburn"
        assert result.raw_data["found"] is True
        assert len(result.extracted_identifiers) > 0
        # Verify that identifiers include ISP and country
        assert any("isp:" in i for i in result.extracted_identifiers)
        assert any("country:" in i for i in result.extracted_identifiers)

    async def test_failed_lookup(self):
        """When ip-api returns status=fail, the scanner should still return SUCCESS with found=False."""
        from src.adapters.scanners.geoip_scanner import GeoIPScanner

        scanner = GeoIPScanner()

        mock_client = _mock_httpx_client({
            "status": "fail",
            "message": "invalid query",
        })

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("not-an-ip", ScanInputType.IP_ADDRESS)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_ip_only(self):
        """GeoIP only supports IP_ADDRESS."""
        from src.adapters.scanners.geoip_scanner import GeoIPScanner

        scanner = GeoIPScanner()
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert not scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== Cert Transparency Scanner ==============


class TestCertTransparencyScanner:
    """Tests for the Certificate Transparency scanner (crt.sh)."""

    async def test_finds_subdomains(self):
        """The scanner should extract unique subdomains from crt.sh certificate entries."""
        from src.adapters.scanners.cert_scanner import CertTransparencyScanner

        scanner = CertTransparencyScanner()

        mock_client = _mock_httpx_client([
            {"common_name": "example.com", "name_value": "www.example.com\nmail.example.com"},
            {"common_name": "*.example.com", "name_value": "api.example.com"},
        ])

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        # Should find www, mail, api subdomains (wildcards are skipped)
        subdomains = result.raw_data["subdomains"]
        assert "www.example.com" in subdomains
        assert "mail.example.com" in subdomains
        assert "api.example.com" in subdomains
        assert result.raw_data["unique_subdomains"] >= 3

    async def test_no_results(self):
        """When crt.sh returns 404, the scanner should report found=False."""
        from src.adapters.scanners.cert_scanner import CertTransparencyScanner

        scanner = CertTransparencyScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent.example", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_domain_only(self):
        """Cert Transparency only supports DOMAIN."""
        from src.adapters.scanners.cert_scanner import CertTransparencyScanner

        scanner = CertTransparencyScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== Breach (HIBP) Scanner ==============


class TestBreachScanner:
    """Tests for the Have I Been Pwned breach scanner."""

    async def test_no_api_key_returns_stub(self):
        """Without an API key, the scanner should return a stub result."""
        from src.adapters.scanners.breach_scanner import BreachScanner

        scanner = BreachScanner()

        with patch("src.adapters.scanners.breach_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(hibp_api_key="")
            result = await scanner.scan("test@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data.get("_stub") is True
        assert result.raw_data["found"] is False

    async def test_breaches_found(self):
        """When the API key is set and breaches exist, they should be returned."""
        from src.adapters.scanners.breach_scanner import BreachScanner

        scanner = BreachScanner()

        mock_client = _mock_httpx_client([
            {
                "Name": "Adobe",
                "Title": "Adobe",
                "Domain": "adobe.com",
                "BreachDate": "2013-10-04",
                "AddedDate": "2013-12-04",
                "PwnCount": 152445165,
                "DataClasses": ["Email addresses", "Passwords"],
                "IsVerified": True,
                "IsSensitive": False,
            }
        ])

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.adapters.scanners.breach_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(hibp_api_key="test-key")
            result = await scanner.scan("test@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["total_breaches"] == 1
        assert result.raw_data["breaches"][0]["name"] == "Adobe"
        assert "breach:Adobe" in result.extracted_identifiers

    async def test_supports_email_only(self):
        """HIBP only supports EMAIL."""
        from src.adapters.scanners.breach_scanner import BreachScanner

        scanner = BreachScanner()
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.USERNAME)


# ============== Phone Scanner ==============


class TestPhoneScanner:
    """Tests for the phone number scanner (uses phonenumbers library, no HTTP)."""

    async def test_valid_polish_phone(self):
        """A valid Polish phone number should be parsed and return country PL.

        If the phonenumbers library is not installed, the scanner returns a stub
        with found=False -- both outcomes are acceptable in a unit test environment.
        """
        from src.adapters.scanners.phone_scanner import PhoneScanner

        scanner = PhoneScanner()

        result = await scanner.scan("+48123456789", ScanInputType.PHONE)
        assert result.status == ScanStatus.SUCCESS

        if result.raw_data.get("_stub"):
            # phonenumbers not installed in test env -- stub is acceptable
            assert result.raw_data["found"] is False
        else:
            assert result.raw_data["found"] is True
            assert result.raw_data["region_code"] == "PL"
            assert result.raw_data["country_code"] == 48

    async def test_valid_us_phone(self):
        """A valid US phone number should be parsed correctly.

        If phonenumbers is unavailable, the stub result is accepted.
        """
        from src.adapters.scanners.phone_scanner import PhoneScanner

        scanner = PhoneScanner()

        result = await scanner.scan("+12025551234", ScanInputType.PHONE)
        assert result.status == ScanStatus.SUCCESS

        if result.raw_data.get("_stub"):
            assert result.raw_data["found"] is False
        else:
            assert result.raw_data["found"] is True
            assert result.raw_data["region_code"] == "US"

    async def test_invalid_phone(self):
        """An unparseable phone number should return found=False gracefully."""
        from src.adapters.scanners.phone_scanner import PhoneScanner

        scanner = PhoneScanner()

        result = await scanner.scan("not-a-phone", ScanInputType.PHONE)
        # Should handle gracefully without raising
        assert result.status in (ScanStatus.SUCCESS, ScanStatus.FAILED)

    async def test_supports_phone_only(self):
        """Phone scanner only supports PHONE."""
        from src.adapters.scanners.phone_scanner import PhoneScanner

        scanner = PhoneScanner()
        assert scanner.supports(ScanInputType.PHONE)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)


# ============== Google Account Scanner ==============


class TestGoogleAccountScanner:
    """Tests for the Google account scanner (probes Gravatar, Calendar, etc.)."""

    async def test_gmail_detection(self):
        """A gmail.com address should be flagged as Gmail and include 'gmail' in services."""
        from src.adapters.scanners.google_scanner import GoogleAccountScanner

        scanner = GoogleAccountScanner()

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.text = "some content"

        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_resp_404.text = ""

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call is Google profile check, second is Gravatar, third is Calendar
            if "gravatar.com" in url:
                return mock_resp_ok
            if "calendar.google.com" in url:
                return mock_resp_404
            return mock_resp_ok

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("test@gmail.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        services = result.raw_data.get("services", [])
        assert "gmail" in services
        assert result.raw_data.get("is_gmail") is True

    async def test_gravatar_detected(self):
        """When Gravatar returns 200, the service should be listed."""
        from src.adapters.scanners.google_scanner import GoogleAccountScanner

        scanner = GoogleAccountScanner()

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.text = ""

        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        mock_resp_404.text = ""

        async def mock_get(url, **kwargs):
            if "gravatar.com" in url:
                return mock_resp_ok
            return mock_resp_404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("user@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert "gravatar" in result.raw_data.get("services", [])

    async def test_supports_email_only(self):
        """Google account scanner only supports EMAIL."""
        from src.adapters.scanners.google_scanner import GoogleAccountScanner

        scanner = GoogleAccountScanner()
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)


# ============== LinkedIn Scanner ==============


class TestLinkedInScanner:
    """Tests for the LinkedIn profile scanner."""

    async def test_profile_found(self):
        """When the LinkedIn profile URL returns 200, the profile should be marked as found."""
        from src.adapters.scanners.linkedin_scanner import LinkedInScanner

        scanner = LinkedInScanner()

        mock_resp_linkedin = MagicMock()
        mock_resp_linkedin.status_code = 200
        mock_resp_linkedin.text = "linkedin.com/in/testuser profile page"
        mock_resp_linkedin.url = "https://www.linkedin.com/in/testuser"

        # Google search returns empty (no LinkedIn URLs found)
        mock_resp_google = MagicMock()
        mock_resp_google.status_code = 200
        mock_resp_google.text = "No results"

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "linkedin.com" in url:
                return mock_resp_linkedin
            return mock_resp_google

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["profiles_found"] >= 1

    async def test_supports_username_and_email(self):
        """LinkedIn supports both USERNAME and EMAIL."""
        from src.adapters.scanners.linkedin_scanner import LinkedInScanner

        scanner = LinkedInScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)


# ============== Twitter Scanner ==============


class TestTwitterScanner:
    """Tests for the Twitter/X profile scanner."""

    async def test_profile_found(self):
        """When the Twitter profile URL returns 200 with the username, it should be marked found."""
        from src.adapters.scanners.twitter_scanner import TwitterScanner

        scanner = TwitterScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<title>testuser (@testuser) / X</title> some content with testuser'

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert "service:twitter" in result.extracted_identifiers

    async def test_profile_not_found(self):
        """When Twitter returns a 'This account doesn' message, the profile should not be found."""
        from src.adapters.scanners.twitter_scanner import TwitterScanner

        scanner = TwitterScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "This account doesn't exist"

        # Nitter returns 404
        mock_resp_nitter = MagicMock()
        mock_resp_nitter.status_code = 404
        mock_resp_nitter.text = "not found"

        async def mock_get(url, **kwargs):
            if "nitter" in url:
                return mock_resp_nitter
            return mock_resp

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent_user_xyz", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_username_only(self):
        """Twitter only supports USERNAME."""
        from src.adapters.scanners.twitter_scanner import TwitterScanner

        scanner = TwitterScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)


# ============== Facebook Scanner ==============


class TestFacebookScanner:
    """Tests for the Facebook profile scanner."""

    async def test_profile_exists(self):
        """When Facebook returns 200 without 'page not found', the profile exists."""
        from src.adapters.scanners.facebook_scanner import FacebookScanner

        scanner = FacebookScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Facebook profile page content"
        mock_resp.url = "https://www.facebook.com/testuser"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["url"] == "https://www.facebook.com/testuser"
        assert "service:facebook" in result.extracted_identifiers

    async def test_profile_not_found(self):
        """When Facebook returns 'page not found', the profile should not be found."""
        from src.adapters.scanners.facebook_scanner import FacebookScanner

        scanner = FacebookScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "This content is not available. Page not found."
        mock_resp.url = "https://www.facebook.com/testuser"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent_user_xyz", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_login_redirect_means_not_found(self):
        """When Facebook redirects to /login, the profile should not be found."""
        from src.adapters.scanners.facebook_scanner import FacebookScanner

        scanner = FacebookScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Login to Facebook"
        mock_resp.url = "https://www.facebook.com/login/?next=..."

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_username_only(self):
        """Facebook only supports USERNAME."""
        from src.adapters.scanners.facebook_scanner import FacebookScanner

        scanner = FacebookScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== Instagram Scanner ==============


class TestInstagramScanner:
    """Tests for the Instagram profile scanner."""

    async def test_api_response_with_user_data(self):
        """When Instagram's web API returns user data, the profile should be populated."""
        from src.adapters.scanners.instagram_scanner import InstagramScanner

        scanner = InstagramScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"user": {
                "full_name": "Test User",
                "biography": "Hello world",
                "edge_followed_by": {"count": 1000},
                "edge_follow": {"count": 500},
                "edge_owner_to_timeline_media": {"count": 50},
                "is_private": False,
                "profile_pic_url": "https://example.com/pic.jpg",
            }}
        }
        mock_resp.text = ""
        mock_resp.url = "https://www.instagram.com/api/v1/users/web_profile_info/"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["followers"] == 1000
        assert result.raw_data["following"] == 500
        assert result.raw_data["posts"] == 50
        assert result.raw_data["full_name"] == "Test User"
        assert "service:instagram" in result.extracted_identifiers

    async def test_fallback_url_check(self):
        """When the API returns a non-200, the scanner falls back to a simple URL check."""
        from src.adapters.scanners.instagram_scanner import InstagramScanner

        scanner = InstagramScanner()

        mock_resp_api = MagicMock()
        mock_resp_api.status_code = 404
        mock_resp_api.text = ""

        mock_resp_page = MagicMock()
        mock_resp_page.status_code = 200
        mock_resp_page.text = "Instagram page content"
        mock_resp_page.url = "https://www.instagram.com/testuser/"

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "api/v1" in url:
                return mock_resp_api
            return mock_resp_page

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True

    async def test_supports_username_only(self):
        """Instagram only supports USERNAME."""
        from src.adapters.scanners.instagram_scanner import InstagramScanner

        scanner = InstagramScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== WHOIS Scanner ==============


class TestWhoisScannerUnit:
    """Tests for the WHOIS scanner (RDAP endpoint)."""

    async def test_domain_lookup(self):
        """A successful WHOIS lookup should extract registrar, nameservers, and dates."""
        from src.adapters.scanners.whois_scanner import WhoisScanner

        scanner = WhoisScanner()

        mock_client = _mock_httpx_client({
            "name": "example.com",
            "entities": [{
                "roles": ["registrar"],
                "vcardArray": ["vcard", [["fn", {}, "text", "Test Registrar"]]],
            }],
            "nameservers": [{"ldhName": "ns1.example.com"}, {"ldhName": "ns2.example.com"}],
            "status": ["active"],
            "events": [
                {"eventAction": "registration", "eventDate": "2000-01-01"},
                {"eventAction": "expiration", "eventDate": "2030-01-01"},
            ],
        })

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["registrar"] == "Test Registrar"
        assert len(result.raw_data["nameservers"]) == 2
        assert result.raw_data["registration_date"] == "2000-01-01"

    async def test_domain_not_found(self):
        """When RDAP returns non-200, the domain should be reported as not found."""
        from src.adapters.scanners.whois_scanner import WhoisScanner

        scanner = WhoisScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent.example", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_domain_only(self):
        """WHOIS only supports DOMAIN."""
        from src.adapters.scanners.whois_scanner import WhoisScanner

        scanner = WhoisScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== DNS Scanner ==============


class TestDNSScannerUnit:
    """Tests for the DNS scanner (Google DNS-over-HTTPS)."""

    async def test_dns_resolution(self):
        """The scanner should resolve A, MX, NS, and TXT records via mocked DNS API."""
        from src.adapters.scanners.dns_scanner import DNSScanner

        scanner = DNSScanner()

        def mock_get(url, **kwargs):
            rtype = kwargs.get("params", {}).get("type", "A")
            resp = MagicMock()
            resp.status_code = 200
            if rtype == "A":
                resp.json.return_value = {"Answer": [{"data": "1.2.3.4"}]}
            elif rtype == "MX":
                resp.json.return_value = {"Answer": [{"data": "10 mail.example.com."}]}
            elif rtype == "NS":
                resp.json.return_value = {"Answer": [{"data": "ns1.example.com."}]}
            elif rtype == "TXT":
                resp.json.return_value = {"Answer": [{"data": "v=spf1 include:_spf.google.com"}]}
            else:
                resp.json.return_value = {"Answer": []}
            return resp

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert "1.2.3.4" in result.raw_data["a_records"]
        assert any("mail.example.com" in mx for mx in result.raw_data["mx_records"])
        assert any("ns1.example.com" in ns for ns in result.raw_data["ns_records"])
        # Verify identifiers were extracted
        assert "ip:1.2.3.4" in result.extracted_identifiers

    async def test_no_records(self):
        """When DNS returns no records, found should be False."""
        from src.adapters.scanners.dns_scanner import DNSScanner

        scanner = DNSScanner()

        def mock_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"Answer": []}
            return resp

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("nonexistent.test", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False

    async def test_supports_domain_only(self):
        """DNS scanner only supports DOMAIN."""
        from src.adapters.scanners.dns_scanner import DNSScanner

        scanner = DNSScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.IP_ADDRESS)


# ============== VirusTotal Scanner ==============


class TestVirusTotalScanner:
    """Tests for the VirusTotal threat intelligence scanner."""

    async def test_no_api_key_returns_stub(self):
        """Without an API key, the scanner should return a stub result."""
        from src.adapters.scanners.virustotal_scanner import VirusTotalScanner

        scanner = VirusTotalScanner()

        with patch("src.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(virustotal_api_key="")
            result = await scanner.scan("example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data.get("_stub") is True

    async def test_with_api_key_domain(self):
        """With an API key, the scanner should query VT and parse analysis stats."""
        from src.adapters.scanners.virustotal_scanner import VirusTotalScanner

        scanner = VirusTotalScanner()

        mock_client = _mock_httpx_client({
            "data": {
                "attributes": {
                    "last_analysis_stats": {
                        "malicious": 2,
                        "suspicious": 1,
                        "harmless": 70,
                        "undetected": 10,
                    },
                    "reputation": -5,
                    "categories": {"Forcepoint ThreatSeeker": "malware"},
                }
            }
        })

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(virustotal_api_key="test-key")
            result = await scanner.scan("malware.example.com", ScanInputType.DOMAIN)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["malicious_detections"] == 2
        assert result.raw_data["suspicious_detections"] == 1
        assert result.raw_data["total_engines"] == 83
        assert "threat:malicious_2" in result.extracted_identifiers

    async def test_supports_domain_ip_url(self):
        """VirusTotal supports DOMAIN, IP_ADDRESS, and URL."""
        from src.adapters.scanners.virustotal_scanner import VirusTotalScanner

        scanner = VirusTotalScanner()
        assert scanner.supports(ScanInputType.DOMAIN)
        assert scanner.supports(ScanInputType.IP_ADDRESS)
        assert scanner.supports(ScanInputType.URL)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== Holehe Scanner ==============


class TestHoleheScanner:
    """Tests for the Holehe email registration scanner."""

    async def test_holehe_import_error_returns_stub(self):
        """When holehe is not installed, the scanner should return a stub result."""
        from src.adapters.scanners.holehe_scanner import HoleheScanner

        scanner = HoleheScanner()

        with patch.dict("sys.modules", {"holehe": None, "holehe.core": None, "holehe.modules": None}):
            result = await scanner.scan("test@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data.get("_stub") is True

    async def test_supports_email_only(self):
        """Holehe only supports EMAIL."""
        from src.adapters.scanners.holehe_scanner import HoleheScanner

        scanner = HoleheScanner()
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.USERNAME)


# ============== Maigret Scanner ==============


class TestMaigretScanner:
    """Tests for the Maigret username scanner."""

    async def test_maigret_import_error_returns_stub(self):
        """When maigret is not installed, the scanner should return a stub result."""
        from src.adapters.scanners.maigret_scanner import MaigretScanner

        scanner = MaigretScanner()

        with patch.dict("sys.modules", {
            "maigret": None,
            "maigret.sites": None,
            "maigret.search": None,
            "maigret.result": None,
        }):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data.get("_stub") is True

    async def test_supports_username_only(self):
        """Maigret only supports USERNAME."""
        from src.adapters.scanners.maigret_scanner import MaigretScanner

        scanner = MaigretScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)


# ============== Playwright CEIDG Scanner ==============


class TestPlaywrightCEIDGScanner:
    """Tests for the Playwright-based CEIDG scanner."""

    async def test_playwright_not_installed_returns_stub(self):
        """When playwright is not installed, the scanner should return a stub."""
        from src.adapters.scanners.playwright_ceidg import PlaywrightCEIDGScanner

        scanner = PlaywrightCEIDGScanner()

        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            result = await scanner.scan("5261040828", ScanInputType.NIP)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data.get("_stub") is True

    async def test_supports_nip_only(self):
        """CEIDG only supports NIP."""
        from src.adapters.scanners.playwright_ceidg import PlaywrightCEIDGScanner

        scanner = PlaywrightCEIDGScanner()
        assert scanner.supports(ScanInputType.NIP)
        assert not scanner.supports(ScanInputType.DOMAIN)


# ============== Playwright KRS Scanner ==============


class TestPlaywrightKRSScanner:
    """Tests for the Playwright-based KRS scanner."""

    async def test_playwright_not_installed_returns_stub(self):
        """When playwright is not installed, the scanner should return a stub."""
        from src.adapters.scanners.playwright_krs import PlaywrightKRSScanner

        scanner = PlaywrightKRSScanner()

        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            result = await scanner.scan("5261040828", ScanInputType.NIP)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data.get("_stub") is True

    async def test_supports_nip_and_domain(self):
        """KRS supports NIP and DOMAIN."""
        from src.adapters.scanners.playwright_krs import PlaywrightKRSScanner

        scanner = PlaywrightKRSScanner()
        assert scanner.supports(ScanInputType.NIP)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)
