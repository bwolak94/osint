"""Toutatis scanner — Instagram account deep info extractor."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_IG_WEB_PROFILE_URL = (
    "https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
)
_IG_FALLBACK_URL = "https://www.instagram.com/{username}/?__a=1&__d=dis"
_IG_HEADERS = {
    "User-Agent": (
        "Instagram 219.0.0.12.117 Android (28/9; 420dpi; 1080x2042; "
        "samsung; SM-G975U; beyond1q; qcom; en_US; 301530837)"
    ),
    "x-ig-app-id": "936619743392459",
    "Accept": "*/*",
    "Accept-Language": "en-US",
    "Connection": "keep-alive",
}


class ToutatisScanner(BaseOsintScanner):
    scanner_name = "toutatis"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip().lstrip("@")

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=_IG_HEADERS,
        ) as client:
            data = await self._fetch_profile(client, username)

        return data

    async def _fetch_profile(self, client: httpx.AsyncClient, username: str) -> dict[str, Any]:
        profile_url = f"https://www.instagram.com/{username}/"

        # Primary endpoint
        user_data: dict[str, Any] | None = None
        try:
            resp = await client.get(_IG_WEB_PROFILE_URL.format(username=username))
            if resp.status_code == 200:
                body = resp.json()
                user_data = (
                    body.get("data", {}).get("user")
                    or body.get("graphql", {}).get("user")
                )
        except Exception as exc:
            log.debug("Instagram primary endpoint failed", username=username, error=str(exc))

        # Fallback endpoint
        if user_data is None:
            try:
                resp = await client.get(_IG_FALLBACK_URL.format(username=username))
                if resp.status_code == 200:
                    body = resp.json()
                    user_data = body.get("graphql", {}).get("user") or body.get("user")
            except Exception as exc:
                log.debug("Instagram fallback endpoint failed", username=username, error=str(exc))

        if user_data is None:
            return {
                "username": username,
                "found": False,
                "profile_url": profile_url,
                "extracted_identifiers": [],
            }

        full_name: str = user_data.get("full_name", "")
        bio: str = user_data.get("biography", "")
        followers: int = (
            user_data.get("edge_followed_by", {}).get("count")
            or user_data.get("follower_count", 0)
        )
        following: int = (
            user_data.get("edge_follow", {}).get("count")
            or user_data.get("following_count", 0)
        )
        posts: int = (
            user_data.get("edge_owner_to_timeline_media", {}).get("count")
            or user_data.get("media_count", 0)
        )
        verified: bool = user_data.get("is_verified", False)
        private: bool = user_data.get("is_private", False)
        external_url: str = user_data.get("external_url", "") or ""
        business_email: str = (
            user_data.get("business_email")
            or user_data.get("public_email", "")
            or ""
        )
        business_phone: str = (
            user_data.get("business_phone_number")
            or user_data.get("public_phone_number", "")
            or ""
        )
        category: str = user_data.get("category_name", "") or user_data.get("category", "") or ""
        profile_pic_url: str = (
            user_data.get("profile_pic_url_hd")
            or user_data.get("profile_pic_url", "")
            or ""
        )

        identifiers: list[str] = []
        if business_email:
            identifiers.append(f"email:{business_email}")
        if external_url:
            identifiers.append(f"url:{external_url}")
        if business_phone:
            identifiers.append(f"phone:{business_phone}")

        return {
            "username": username,
            "found": True,
            "full_name": full_name,
            "bio": bio,
            "followers": followers,
            "following": following,
            "posts": posts,
            "verified": verified,
            "private": private,
            "profile_url": profile_url,
            "profile_pic_url": profile_pic_url,
            "external_url": external_url,
            "business_email": business_email,
            "business_phone": business_phone,
            "category": category,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
