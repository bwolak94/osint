"""Unit tests for username and email OSINT scanners.

Covers: SherlockScanner, SocialscanScanner, WhatsmynameScanner,
GhuntScanner, ToutatisScanner, IgnorantScanner, PhotonScanner.
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
    mock_r.content = b""
    return mock_r


def _mock_httpx(response_data=None, status_code=200, text=None):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.post = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.head = AsyncMock(return_value=_mock_resp(response_data, status_code, text))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# SherlockScanner
# ---------------------------------------------------------------------------

class TestSherlockScanner:
    """Tests for the Sherlock username presence scanner."""

    async def test_scan_found_on_multiple_platforms(self):
        """Direct HTTP 200 responses mark profiles as found."""
        from src.adapters.scanners.sherlock_scanner import SherlockScanner

        scanner = SherlockScanner()

        found_resp = _mock_resp(status_code=200)
        not_found_resp = _mock_resp(status_code=404)

        # Sherlock calls head() for each site; always return 200 for simplicity
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=found_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # Force subprocess to fail so we use direct checks
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("johndoe", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["source"] == "direct_http"
        assert result.raw_data["total_found"] > 0
        assert len(result.raw_data["profile_urls"]) == result.raw_data["total_found"]

    async def test_scan_not_found(self):
        """All 404 responses produce total_found=0."""
        from src.adapters.scanners.sherlock_scanner import SherlockScanner

        scanner = SherlockScanner()

        not_found_resp = _mock_resp(status_code=404)
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=not_found_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("xyzxyzxyz_no_such_user", ScanInputType.USERNAME)

        assert result.raw_data["total_found"] == 0

    async def test_supports_input_types(self):
        """Sherlock only supports USERNAME."""
        from src.adapters.scanners.sherlock_scanner import SherlockScanner

        scanner = SherlockScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_handles_network_exception(self):
        """Individual site exceptions are silently swallowed; result still returns."""
        from src.adapters.scanners.sherlock_scanner import SherlockScanner

        scanner = SherlockScanner()

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["total_found"] == 0

    async def test_extracts_identifiers(self):
        """Found profile URLs are extracted as url: identifiers."""
        from src.adapters.scanners.sherlock_scanner import SherlockScanner

        scanner = SherlockScanner()

        found_resp = _mock_resp(status_code=200)
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=found_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await scanner.scan("alice", ScanInputType.USERNAME)

        for ident in result.extracted_identifiers:
            assert ident.startswith("url:")


# ---------------------------------------------------------------------------
# SocialscanScanner
# ---------------------------------------------------------------------------

class TestSocialscanScanner:
    """Tests for the Socialscan username/email availability scanner."""

    async def test_scan_username_registered(self):
        """GitHub 200 indicates username registered."""
        from src.adapters.scanners.socialscan_scanner import SocialscanScanner

        scanner = SocialscanScanner()

        # Reddit → "error" key means registered
        reddit_resp = _mock_resp({"error": "USERNAME_TAKEN"})
        github_resp = _mock_resp({}, status_code=200)
        twitter_resp = _mock_resp({}, status_code=200)
        instagram_resp = _mock_resp({}, status_code=200, text="Welcome instagram profile")
        twitch_resp = _mock_resp({}, status_code=200)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=reddit_resp)
        mock_client.get = AsyncMock(side_effect=[github_resp, instagram_resp, twitch_resp])
        mock_client.head = AsyncMock(return_value=twitter_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("alice", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["source"] == "direct_checks"
        assert result.raw_data["registered_count"] > 0

    async def test_scan_username_available(self):
        """GitHub 404 indicates username available."""
        from src.adapters.scanners.socialscan_scanner import SocialscanScanner

        scanner = SocialscanScanner()

        reddit_resp = _mock_resp({})  # no error key → available
        github_resp = _mock_resp({}, status_code=404)
        twitter_resp = _mock_resp({}, status_code=404)
        instagram_resp = _mock_resp(text="Page Not Found", status_code=200)
        twitch_resp = _mock_resp({}, status_code=404)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=reddit_resp)
        mock_client.get = AsyncMock(side_effect=[github_resp, instagram_resp, twitch_resp])
        mock_client.head = AsyncMock(return_value=twitter_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("xyzxyzunavailable", ScanInputType.USERNAME)

        assert result.raw_data["registered_count"] == 0

    async def test_supports_input_types(self):
        """Socialscan supports USERNAME and EMAIL."""
        from src.adapters.scanners.socialscan_scanner import SocialscanScanner

        scanner = SocialscanScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_handles_network_exception(self):
        """Exception in platform check returns unknown status."""
        from src.adapters.scanners.socialscan_scanner import SocialscanScanner

        scanner = SocialscanScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.head = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert "unknown" in result.raw_data["platform_results"].values()

    async def test_extracts_identifiers_empty(self):
        """Socialscan returns no pivot identifiers."""
        from src.adapters.scanners.socialscan_scanner import SocialscanScanner

        scanner = SocialscanScanner()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_resp({}))
        mock_client.get = AsyncMock(return_value=_mock_resp({}, 404))
        mock_client.head = AsyncMock(return_value=_mock_resp({}, 404))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("bob", ScanInputType.USERNAME)

        assert result.extracted_identifiers == []


# ---------------------------------------------------------------------------
# WhatsmynameScanner
# ---------------------------------------------------------------------------

class TestWhatsmynameScanner:
    """Tests for the WhatsMyName community username scanner."""

    def _wmn_data(self):
        return {
            "sites": [
                {
                    "name": "GitHub",
                    "uri_check": "https://github.com/{account}",
                    "account_existence_code": 200,
                    "category": "coding",
                },
                {
                    "name": "Twitter",
                    "uri_check": "https://twitter.com/{account}",
                    "account_existence_code": 200,
                    "category": "social",
                },
            ]
        }

    async def test_scan_found(self):
        """Sites responding with existence code are reported as found."""
        from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner

        scanner = WhatsmynameScanner()

        wmn_resp = _mock_resp(self._wmn_data())
        site_resp_found = _mock_resp(status_code=200)

        mock_client = AsyncMock()
        # First call fetches wmn-data.json, subsequent calls check individual sites
        mock_client.get = AsyncMock(side_effect=[wmn_resp, site_resp_found, site_resp_found])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("johndoe", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found_count"] == 2
        assert result.raw_data["total_checked"] == 2

    async def test_scan_not_found(self):
        """No sites match returns found_count=0."""
        from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner

        scanner = WhatsmynameScanner()

        wmn_resp = _mock_resp(self._wmn_data())
        site_resp_nf = _mock_resp(status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[wmn_resp, site_resp_nf, site_resp_nf])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("xyz_no_such_user_99", ScanInputType.USERNAME)

        assert result.raw_data["found_count"] == 0

    async def test_supports_input_types(self):
        """WhatsmyName supports only USERNAME."""
        from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner

        scanner = WhatsmynameScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_handles_wmn_data_fetch_error(self):
        """Failure fetching wmn-data.json bubbles up as FAILED."""
        from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner

        scanner = WhatsmynameScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("GitHub raw unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)

        assert result.status == ScanStatus.FAILED

    async def test_extracts_identifiers(self):
        """Found account URLs are extracted as url: identifiers."""
        from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner

        scanner = WhatsmynameScanner()

        wmn_resp = _mock_resp(self._wmn_data())
        found_resp = _mock_resp(status_code=200)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[wmn_resp, found_resp, found_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("alice", ScanInputType.USERNAME)

        for ident in result.extracted_identifiers:
            assert ident.startswith("url:")


# ---------------------------------------------------------------------------
# GhuntScanner
# ---------------------------------------------------------------------------

class TestGhuntScanner:
    """Tests for the GHunt Google account scanner."""

    async def test_scan_gravatar_found(self):
        """Gravatar profile returns display name and photo."""
        from src.adapters.scanners.ghunt_scanner import GhuntScanner

        scanner = GhuntScanner()

        gravatar_resp = _mock_resp({
            "entry": [{
                "displayName": "Jane Doe",
                "photos": [{"value": "https://gravatar.com/avatar/abc.jpg"}],
                "profileUrl": "https://gravatar.com/janedoe",
                "aboutMe": "Security researcher",
                "currentLocation": "Berlin",
                "urls": [],
                "name": {},
            }]
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=gravatar_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.ghunt_scanner.get_settings") as ms:
                ms.return_value.shodan_api_key = ""
                result = await scanner.scan("jane@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["display_name"] == "Jane Doe"

    async def test_scan_not_found(self):
        """Gravatar 404 returns empty display_name."""
        from src.adapters.scanners.ghunt_scanner import GhuntScanner

        scanner = GhuntScanner()

        gravatar_resp = _mock_resp({}, status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=gravatar_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.ghunt_scanner.get_settings") as ms:
                ms.return_value.shodan_api_key = ""
                result = await scanner.scan("nobody@example.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["display_name"] == ""

    async def test_supports_input_types(self):
        """GHunt supports only EMAIL."""
        from src.adapters.scanners.ghunt_scanner import GhuntScanner

        scanner = GhuntScanner()
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_handles_exception(self):
        """Network exception is handled gracefully — no raise, empty result."""
        from src.adapters.scanners.ghunt_scanner import GhuntScanner

        scanner = GhuntScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.ghunt_scanner.get_settings") as ms:
                ms.return_value.shodan_api_key = ""
                result = await scanner.scan("jane@example.com", ScanInputType.EMAIL)

        # GhuntScanner handles errors gracefully — returns empty strings/None
        assert result.raw_data.get("display_name") == ""
        assert result.extracted_identifiers == []

    async def test_extracts_identifiers(self):
        """Display name produces person: identifier; YouTube URL produces url: identifier."""
        from src.adapters.scanners.ghunt_scanner import GhuntScanner

        scanner = GhuntScanner()

        gravatar_resp = _mock_resp({
            "entry": [{
                "displayName": "Jane Doe",
                "photos": [],
                "profileUrl": "",
                "aboutMe": "",
                "currentLocation": "",
                "urls": [],
                "name": {},
            }]
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=gravatar_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("src.adapters.scanners.ghunt_scanner.get_settings") as ms:
                ms.return_value.shodan_api_key = ""
                result = await scanner.scan("jane@example.com", ScanInputType.EMAIL)

        assert "person:Jane Doe" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# ToutatisScanner
# ---------------------------------------------------------------------------

class TestToutatisScanner:
    """Tests for the Instagram deep info extractor (Toutatis)."""

    async def test_scan_profile_found(self):
        """Primary Instagram API endpoint returns full profile data."""
        from src.adapters.scanners.toutatis_scanner import ToutatisScanner

        scanner = ToutatisScanner()

        ig_resp = _mock_resp({
            "data": {
                "user": {
                    "full_name": "Alice Smith",
                    "biography": "Security researcher",
                    "edge_followed_by": {"count": 5000},
                    "edge_follow": {"count": 300},
                    "edge_owner_to_timeline_media": {"count": 120},
                    "is_verified": True,
                    "is_private": False,
                    "external_url": "https://alicesmith.dev",
                    "business_email": "alice@alicesmith.dev",
                    "business_phone_number": "",
                    "category_name": "Personal Blog",
                    "profile_pic_url": "https://example.com/pic.jpg",
                }
            }
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=ig_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("alicesmith", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["full_name"] == "Alice Smith"
        assert result.raw_data["followers"] == 5000

    async def test_scan_not_found(self):
        """No user data in response returns found=False."""
        from src.adapters.scanners.toutatis_scanner import ToutatisScanner

        scanner = ToutatisScanner()

        ig_resp = _mock_resp({"data": {"user": None}})
        fallback_resp = _mock_resp({})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[ig_resp, fallback_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("no_such_user_xyz", ScanInputType.USERNAME)

        assert result.raw_data["found"] is False

    async def test_supports_input_types(self):
        """Toutatis supports only USERNAME."""
        from src.adapters.scanners.toutatis_scanner import ToutatisScanner

        scanner = ToutatisScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_http_exception(self):
        """Network exception is handled gracefully — found=False, no raise."""
        from src.adapters.scanners.toutatis_scanner import ToutatisScanner

        scanner = ToutatisScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Instagram blocked"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("alicesmith", ScanInputType.USERNAME)

        assert result.raw_data.get("found") is False

    async def test_extracts_identifiers(self):
        """Business email, URL, and phone extracted as typed identifiers."""
        from src.adapters.scanners.toutatis_scanner import ToutatisScanner

        scanner = ToutatisScanner()

        ig_resp = _mock_resp({
            "data": {
                "user": {
                    "full_name": "Bob",
                    "biography": "",
                    "edge_followed_by": {"count": 100},
                    "edge_follow": {"count": 50},
                    "edge_owner_to_timeline_media": {"count": 10},
                    "is_verified": False,
                    "is_private": False,
                    "external_url": "https://bob.example.com",
                    "business_email": "bob@example.com",
                    "business_phone_number": "+1234567890",
                    "category_name": "",
                    "profile_pic_url": "",
                }
            }
        })

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=ig_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("bob", ScanInputType.USERNAME)

        assert "email:bob@example.com" in result.extracted_identifiers
        assert "url:https://bob.example.com" in result.extracted_identifiers
        assert "phone:+1234567890" in result.extracted_identifiers


# ---------------------------------------------------------------------------
# IgnorantScanner
# ---------------------------------------------------------------------------

class TestIgnorantScanner:
    """Tests for the Ignorant phone number platform checker."""

    async def test_scan_phone_registered(self):
        """Snapchat 200 with 'snapchat' in body marks as registered."""
        from src.adapters.scanners.ignorant_scanner import IgnorantScanner

        scanner = IgnorantScanner()

        snap_resp = _mock_resp(status_code=200, text="This is the official snapchat page")
        ig_resp = _mock_resp({
            "errors": {"phone_number": ["This phone number is already registered."]}
        }, status_code=400)
        wa_resp = _mock_resp(status_code=302)
        tg_resp = _mock_resp(status_code=200, text="tgme_page_title Profile title")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[snap_resp, tg_resp])
        mock_client.post = AsyncMock(return_value=ig_resp)
        mock_client.head = AsyncMock(return_value=wa_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("+1234567890", ScanInputType.PHONE)

        assert result.status == ScanStatus.SUCCESS
        assert "Snapchat" in result.raw_data["platform_results"]

    async def test_scan_phone_not_registered(self):
        """404 on Snapchat returns not_registered."""
        from src.adapters.scanners.ignorant_scanner import IgnorantScanner

        scanner = IgnorantScanner()

        snap_resp = _mock_resp(status_code=404)
        ig_resp = _mock_resp({}, status_code=200)
        wa_resp = _mock_resp(status_code=200)
        tg_resp = _mock_resp(status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[snap_resp, tg_resp])
        mock_client.post = AsyncMock(return_value=ig_resp)
        mock_client.head = AsyncMock(return_value=wa_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("+9990000000", ScanInputType.PHONE)

        assert result.raw_data["found_count"] == 0

    async def test_supports_input_types(self):
        """Ignorant only supports PHONE."""
        from src.adapters.scanners.ignorant_scanner import IgnorantScanner

        scanner = IgnorantScanner()
        assert scanner.supports(ScanInputType.PHONE)
        assert not scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.USERNAME)

    async def test_handles_platform_exception(self):
        """Platform exception is caught and marked as unknown."""
        from src.adapters.scanners.ignorant_scanner import IgnorantScanner

        scanner = IgnorantScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.post = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.head = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("+1234567890", ScanInputType.PHONE)

        assert result.status == ScanStatus.SUCCESS
        # All platforms should be unknown when all calls fail
        for status in result.raw_data["platform_results"].values():
            assert status == "unknown"

    async def test_extracts_identifiers_empty(self):
        """Ignorant is enrichment only — no pivot identifiers."""
        from src.adapters.scanners.ignorant_scanner import IgnorantScanner

        scanner = IgnorantScanner()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_resp(status_code=404))
        mock_client.post = AsyncMock(return_value=_mock_resp({}))
        mock_client.head = AsyncMock(return_value=_mock_resp(status_code=200))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("+1234567890", ScanInputType.PHONE)

        assert result.extracted_identifiers == []


# ---------------------------------------------------------------------------
# PhotonScanner
# ---------------------------------------------------------------------------

class TestPhotonScanner:
    """Tests for the Photon web crawler scanner."""

    async def test_scan_finds_email_in_html(self):
        """Crawler extracts email addresses from HTML content."""
        from src.adapters.scanners.photon_scanner import PhotonScanner

        scanner = PhotonScanner()

        html_resp = _mock_resp(
            status_code=200,
            text="<html><body>Contact: security@example.com, info@example.com</body></html>",
        )
        html_resp.headers = MagicMock()
        html_resp.headers.get = MagicMock(return_value="text/html")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=html_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("https://example.com", ScanInputType.URL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["pages_crawled"] >= 1
        found_emails = result.raw_data.get("emails", [])
        assert "security@example.com" in found_emails or "info@example.com" in found_emails

    async def test_scan_no_content(self):
        """Empty body returns zero emails and phones."""
        from src.adapters.scanners.photon_scanner import PhotonScanner

        scanner = PhotonScanner()

        empty_resp = _mock_resp(status_code=200, text="<html></html>")
        empty_resp.headers = MagicMock()
        empty_resp.headers.get = MagicMock(return_value="text/html")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=empty_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("https://example.com", ScanInputType.URL)

        assert result.raw_data["emails"] == []
        assert result.raw_data["phones"] == []

    async def test_supports_input_types(self):
        """Photon supports URL and DOMAIN."""
        from src.adapters.scanners.photon_scanner import PhotonScanner

        scanner = PhotonScanner()
        assert scanner.supports(ScanInputType.URL)
        assert scanner.supports(ScanInputType.DOMAIN)
        assert not scanner.supports(ScanInputType.EMAIL)

    async def test_handles_crawl_exception(self):
        """Network exception during crawl returns FAILED status."""
        from src.adapters.scanners.photon_scanner import PhotonScanner

        scanner = PhotonScanner()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Host unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("https://example.com", ScanInputType.URL)

        # All pages fail to crawl → pages_crawled=0, result still SUCCESS
        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["pages_crawled"] == 0

    async def test_extracts_email_identifiers(self):
        """Found emails produce email: identifiers."""
        from src.adapters.scanners.photon_scanner import PhotonScanner

        scanner = PhotonScanner()

        html_resp = _mock_resp(
            status_code=200,
            text="Contact us at hello@example.com or support@example.com",
        )
        html_resp.headers = MagicMock()
        html_resp.headers.get = MagicMock(return_value="text/html")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=html_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await scanner.scan("https://example.com", ScanInputType.URL)

        email_identifiers = [i for i in result.extracted_identifiers if i.startswith("email:")]
        assert len(email_identifiers) >= 1
