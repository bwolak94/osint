"""Instagram scanner — checks for Instagram profile existence and public data."""

from typing import Any
import structlog
from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class InstagramScanner(BaseOsintScanner):
    """Checks if a username has an Instagram profile.

    Queries the Instagram web API for public profile data
    including bio, follower count, and post count.
    """

    scanner_name = "instagram"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            profile: dict[str, Any] = {
                "username": input_value,
                "platform": "instagram",
                "found": False,
                "url": None,
                "full_name": None,
                "bio": None,
                "followers": None,
                "following": None,
                "posts": None,
                "is_private": None,
                "profile_pic": None,
            }
            identifiers: list[str] = []

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                # Try Instagram's web API (works for public profiles)
                try:
                    resp = await client.get(
                        f"https://www.instagram.com/api/v1/users/web_profile_info/?username={input_value}",
                        headers={
                            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)",
                            "X-IG-App-ID": "936619743392459",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        user = data.get("data", {}).get("user", {})
                        if user:
                            profile["found"] = True
                            profile["url"] = f"https://www.instagram.com/{input_value}/"
                            profile["full_name"] = user.get("full_name")
                            profile["bio"] = user.get("biography")
                            profile["followers"] = user.get("edge_followed_by", {}).get("count")
                            profile["following"] = user.get("edge_follow", {}).get("count")
                            profile["posts"] = user.get("edge_owner_to_timeline_media", {}).get("count")
                            profile["is_private"] = user.get("is_private")
                            profile["profile_pic"] = user.get("profile_pic_url_hd") or user.get("profile_pic_url")

                            identifiers.append(f"url:https://www.instagram.com/{input_value}/")
                            identifiers.append("service:instagram")
                            if profile["full_name"]:
                                identifiers.append(f"name:{profile['full_name']}")
                except Exception:
                    pass

                # Fallback: simple URL check
                if not profile["found"]:
                    try:
                        resp = await client.get(
                            f"https://www.instagram.com/{input_value}/",
                            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                        )
                        if resp.status_code == 200 and "/login" not in str(resp.url) and "page not found" not in resp.text.lower():
                            profile["found"] = True
                            profile["url"] = f"https://www.instagram.com/{input_value}/"
                            identifiers.append(f"url:https://www.instagram.com/{input_value}/")
                            identifiers.append("service:instagram")
                    except Exception:
                        pass

            profile["extracted_identifiers"] = identifiers
            return profile

        except ImportError:
            return {"username": input_value, "found": False, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("Instagram scan error", error=str(e))
            raise
