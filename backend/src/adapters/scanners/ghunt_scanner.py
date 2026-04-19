"""GHunt scanner — Google account OSINT via public APIs and Gravatar."""

import hashlib
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class GhuntScanner(BaseOsintScanner):
    scanner_name = "ghunt"
    supported_input_types = frozenset({ScanInputType.EMAIL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        email = input_value.strip().lower()
        settings = get_settings()

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        ) as client:
            gravatar = await self._check_gravatar(client, email)
            youtube_channel = await self._check_youtube(client, email, settings.shodan_api_key)

        display_name: str = gravatar.get("display_name", "")
        profile_photo: str = gravatar.get("profile_photo", "")
        identifiers: list[str] = []

        if youtube_channel.get("url"):
            identifiers.append(f"url:{youtube_channel['url']}")
        if display_name:
            identifiers.append(f"person:{display_name}")

        return {
            "email": email,
            "gmail_exists": None,  # Requires cookie auth; skipped for safety
            "google_id": gravatar.get("google_id"),
            "display_name": display_name,
            "profile_photo": profile_photo,
            "youtube_channel": youtube_channel,
            "gravatar_profile": gravatar,
            "maps_contributions": False,
            "extracted_identifiers": identifiers,
        }

    async def _check_gravatar(self, client: httpx.AsyncClient, email: str) -> dict[str, Any]:
        """Fetch Gravatar profile for the given email."""
        email_hash = hashlib.md5(email.encode()).hexdigest()  # noqa: S324
        url = f"https://www.gravatar.com/{email_hash}.json"
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {}
            data = resp.json()
            entry = data.get("entry", [{}])[0]
            name_info = entry.get("name", {})
            display_name = entry.get("displayName", "") or name_info.get("formatted", "")
            photos = entry.get("photos", [])
            profile_photo = photos[0].get("value", "") if photos else ""
            return {
                "display_name": display_name,
                "profile_photo": profile_photo,
                "profile_url": entry.get("profileUrl", ""),
                "about_me": entry.get("aboutMe", ""),
                "location": entry.get("currentLocation", ""),
                "urls": [u.get("value", "") for u in entry.get("urls", [])],
                "google_id": None,
            }
        except Exception as exc:
            log.debug("Gravatar lookup failed", email=email, error=str(exc))
            return {}

    async def _check_youtube(
        self,
        client: httpx.AsyncClient,
        email: str,
        youtube_api_key: str,
    ) -> dict[str, Any]:
        """Search YouTube for a channel matching the email address."""
        if not youtube_api_key:
            return {}
        try:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "q": email,
                    "type": "channel",
                    "part": "snippet",
                    "maxResults": "1",
                    "key": youtube_api_key,
                },
            )
            if resp.status_code != 200:
                return {}
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return {}
            snippet = items[0].get("snippet", {})
            channel_id = items[0].get("id", {}).get("channelId", "")
            return {
                "channel_id": channel_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else "",
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            }
        except Exception as exc:
            log.debug("YouTube channel lookup failed", email=email, error=str(exc))
            return {}

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
