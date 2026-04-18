"""GitHub OSINT scanner — queries the GitHub API for user intelligence."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class GitHubScanner(BaseOsintScanner):
    """Queries the GitHub API for public user profile information.

    Supports USERNAME (direct profile lookup) and EMAIL (search then profile fetch).
    If a github_api_token is configured, it is used for higher rate limits.
    """

    scanner_name = "github"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 21600  # 6 hours

    def _build_headers(self) -> dict[str, str]:
        """Build request headers, optionally including auth token."""
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        settings = get_settings()
        if settings.github_api_token:
            headers["Authorization"] = f"Bearer {settings.github_api_token}"
        return headers

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if input_type == ScanInputType.USERNAME:
            return await self._fetch_user_profile(input_value)

        if input_type == ScanInputType.EMAIL:
            return await self._search_by_email(input_value)

        return {
            "input": input_value,
            "found": False,
            "error": f"Unsupported input type: {input_type}",
            "extracted_identifiers": [],
        }

    async def _fetch_user_profile(self, username: str) -> dict[str, Any]:
        """Fetch a GitHub user profile by username."""
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/users/{username}",
                headers=headers,
            )

            if resp.status_code == 404:
                return {
                    "input": username,
                    "found": False,
                    "extracted_identifiers": [],
                }

            resp.raise_for_status()
            data = resp.json()

        return self._format_profile(data)

    async def _search_by_email(self, email: str) -> dict[str, Any]:
        """Search GitHub users by email, then fetch the first match's profile."""
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.github.com/search/users",
                params={"q": f"{email}+in:email"},
                headers=headers,
            )

            resp.raise_for_status()
            search_data = resp.json()

            items = search_data.get("items", [])
            if not items:
                return {
                    "input": email,
                    "found": False,
                    "extracted_identifiers": [],
                }

            # Fetch the full profile of the first matching user
            login = items[0].get("login", "")
            profile_resp = await client.get(
                f"https://api.github.com/users/{login}",
                headers=headers,
            )
            profile_resp.raise_for_status()
            profile_data = profile_resp.json()

        return self._format_profile(profile_data)

    def _format_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Format a GitHub user profile into a standardised result dict."""
        login = data.get("login", "")
        email = data.get("email")
        blog = data.get("blog")

        identifiers: list[str] = []
        if login:
            identifiers.append(f"username:{login}")
        if blog:
            identifiers.append(f"url:{blog}")
        if email:
            identifiers.append(f"email:{email}")

        return {
            "input": login,
            "found": True,
            "username": login,
            "name": data.get("name"),
            "company": data.get("company"),
            "location": data.get("location"),
            "bio": data.get("bio"),
            "blog": blog,
            "public_repos": data.get("public_repos", 0),
            "followers": data.get("followers", 0),
            "following": data.get("following", 0),
            "created_at": data.get("created_at"),
            "avatar_url": data.get("avatar_url"),
            "extracted_identifiers": identifiers,
        }
