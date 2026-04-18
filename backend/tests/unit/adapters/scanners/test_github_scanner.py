"""Unit tests for the GitHub OSINT scanner."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adapters.scanners.github_scanner import GitHubScanner
from src.core.domain.entities.types import ScanInputType, ScanStatus


def _mock_httpx_client(response_data, status_code=200):
    """Create a mock httpx.AsyncClient context manager."""
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


_SAMPLE_PROFILE = {
    "login": "octocat",
    "name": "The Octocat",
    "company": "GitHub",
    "blog": "https://github.blog",
    "location": "San Francisco",
    "email": "octocat@github.com",
    "bio": "A friendly cat",
    "public_repos": 42,
    "public_gists": 10,
    "followers": 1000,
    "following": 5,
    "created_at": "2011-01-25T18:44:36Z",
    "avatar_url": "https://avatars.githubusercontent.com/u/583231",
}


class TestGitHubScanner:
    """Tests for the GitHub scanner."""

    async def test_github_username_success(self):
        """Fetching a user by username returns a populated profile."""
        scanner = GitHubScanner()
        mock_client = _mock_httpx_client(_SAMPLE_PROFILE)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.adapters.scanners.github_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_api_token="")
            result = await scanner.scan("octocat", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["username"] == "octocat"
        assert result.raw_data["public_repos"] == 42
        assert "username:octocat" in result.extracted_identifiers
        assert "url:https://github.blog" in result.extracted_identifiers
        assert "email:octocat@github.com" in result.extracted_identifiers

    async def test_github_email_search(self):
        """Searching by email finds a user and fetches their profile."""
        scanner = GitHubScanner()

        search_response = {"total_count": 1, "items": [{"login": "octocat"}]}

        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.raise_for_status = MagicMock()
        mock_search_resp.json.return_value = search_response

        mock_profile_resp = MagicMock()
        mock_profile_resp.status_code = 200
        mock_profile_resp.raise_for_status = MagicMock()
        mock_profile_resp.json.return_value = _SAMPLE_PROFILE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[mock_search_resp, mock_profile_resp])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.adapters.scanners.github_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_api_token="")
            result = await scanner.scan("octocat@github.com", ScanInputType.EMAIL)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is True
        assert result.raw_data["username"] == "octocat"

    async def test_github_supports_username_and_email(self):
        """GitHub scanner supports USERNAME and EMAIL but not DOMAIN."""
        scanner = GitHubScanner()
        assert scanner.supports(ScanInputType.USERNAME)
        assert scanner.supports(ScanInputType.EMAIL)
        assert not scanner.supports(ScanInputType.DOMAIN)

    async def test_github_user_not_found(self):
        """A 404 response returns found=False."""
        scanner = GitHubScanner()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"message": "Not Found"}
        mock_resp.text = "Not Found"
        mock_resp.url = "https://api.github.com/users/nonexistent"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("src.adapters.scanners.github_scanner.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_api_token="")
            result = await scanner.scan("nonexistent_user_xyz", ScanInputType.USERNAME)

        assert result.status == ScanStatus.SUCCESS
        assert result.raw_data["found"] is False
        assert result.extracted_identifiers == []
