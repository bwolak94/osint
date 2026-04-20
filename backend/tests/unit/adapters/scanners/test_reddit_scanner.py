"""Tests for Reddit scanner."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = response_data
    mock_resp.text = str(response_data)
    mock_resp.url = "https://reddit.com"
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestRedditScanner:
    async def test_reddit_found(self):
        from src.adapters.scanners.reddit_scanner import RedditScanner

        scanner = RedditScanner()
        mock = _mock_httpx_client({
            "data": {
                "comment_karma": 100,
                "link_karma": 50,
                "verified": True,
                "has_verified_email": True,
                "subreddit": {"display_name_prefixed": "u/testuser"},
            }
        })
        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("testuser", ScanInputType.USERNAME)
        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["comment_karma"] == 100

    async def test_reddit_supports_username(self):
        from src.adapters.scanners.reddit_scanner import RedditScanner

        scanner = RedditScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_reddit_not_found(self):
        from src.adapters.scanners.reddit_scanner import RedditScanner

        scanner = RedditScanner()
        mock = _mock_httpx_client({}, status_code=404)
        with patch("httpx.AsyncClient", return_value=mock):
            result = await scanner.scan("nonexistent", ScanInputType.USERNAME)
        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
