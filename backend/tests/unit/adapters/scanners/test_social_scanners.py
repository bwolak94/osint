"""Tests for TikTok and YouTube scanners."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_text="", status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = response_text
    mock_resp.url = "https://example.com"
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestTikTokScanner:
    async def test_tiktok_found(self):
        from src.adapters.scanners.tiktok_scanner import TikTokScanner

        scanner = TikTokScanner()
        mock = _mock_httpx_client(response_text="Welcome @testuser profile page")
        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)
        assert result.status == ScanStatus.SUCCESS

    async def test_tiktok_supports_username(self):
        from src.adapters.scanners.tiktok_scanner import TikTokScanner

        assert TikTokScanner().supports(ScanInputType.USERNAME)
        assert not TikTokScanner().supports(ScanInputType.EMAIL)


class TestYouTubeScanner:
    async def test_youtube_found(self):
        from src.adapters.scanners.youtube_scanner import YouTubeScanner

        scanner = YouTubeScanner()
        mock = _mock_httpx_client(response_text="YouTube channel page")
        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)
        assert result.status == ScanStatus.SUCCESS

    async def test_youtube_supports_username(self):
        from src.adapters.scanners.youtube_scanner import YouTubeScanner

        assert YouTubeScanner().supports(ScanInputType.USERNAME)
        assert not YouTubeScanner().supports(ScanInputType.DOMAIN)
