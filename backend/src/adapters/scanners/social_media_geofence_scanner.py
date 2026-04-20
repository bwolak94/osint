"""Social Media Geofence Scanner — aggregate geo-tagged posts near coordinates.

OPSEC intelligence value:
  - Geo-tagged social media posts near a target location provide a timeline of human activity.
  - Photos posted at a location may contain additional identifiers: faces, vehicle plates,
    device metadata, and timestamp data confirming presence at a specific time.
  - Flickr's public API provides free geo-tagged image search without authentication,
    enabling rapid location intelligence without requiring target-specific accounts.
  - Twitter/X geo-search can surface real-time posts near an event or facility.
  - Analysts should cross-reference post timestamps against known target schedules.

Input entities:  COORDINATES — "lat,lon[,radius_km]" decimal string
Output entities:
  - posts_found         — list of aggregated post metadata from available platforms
  - platform_coverage   — dict of platforms with result counts
  - search_urls         — manual investigation links for each platform
  - search_radius_km    — effective search radius used
  - educational_note    — geofence OSINT methodology
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_FLICKR_API_URL = "https://www.flickr.com/services/rest/"
_TWITTER_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "Geofence-based social media OSINT methodology: "
    "1) Geo-tagged post aggregation — platforms that allow location search (Flickr, Twitter, "
    "   Instagram) can surface posts within a radius of any coordinates. "
    "2) Timeline construction — sort posts by timestamp to identify activity patterns "
    "   (morning delivery routines, shift changes, events). "
    "3) Author pivot — each post author becomes a new OSINT seed (username, profile, network). "
    "4) Visual intelligence — images from nearby posts may show building access points, "
    "   security posture, vehicle types, and personnel. "
    "5) Negative space analysis — absence of posts from an active area is also intelligence "
    "   (possible restricted zone, communications blackout, or rural remoteness). "
    "6) Always respect platform ToS and applicable laws when collecting personal data."
)

_DEFAULT_RADIUS_KM = 1.0
_MAX_RADIUS_KM = 32.0


def _build_twitter_manual_url(lat: float, lon: float, radius_km: float) -> str:
    return (
        f"https://twitter.com/search?q=geocode%3A{lat}%2C{lon}%2C{radius_km}km&f=live"
    )


def _build_instagram_manual_url(lat: float, lon: float) -> str:
    return f"https://www.instagram.com/explore/locations/?lat={lat}&lng={lon}"


def _build_flickr_manual_url(lat: float, lon: float, radius_km: float) -> str:
    return (
        f"https://www.flickr.com/map/?fLat={lat}&fLon={lon}&zl=14&search=1"
        f"&q=&sort=relevance&radius={radius_km}"
    )


def _build_google_maps_nearby_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/@{lat},{lon},15z"


def _build_yandex_maps_url(lat: float, lon: float) -> str:
    return f"https://yandex.com/maps/?ll={lon},{lat}&z=15"


class SocialMediaGeofenceScanner(BaseOsintScanner):
    """Search geo-tagged social media posts near given coordinates.

    Input:  ScanInputType.COORDINATES — "lat,lon[,radius_km]" string.
    Output: posts_found list, platform_coverage dict, search_urls dict.

    Optional environment variables:
      - TWITTER_BEARER_TOKEN — Twitter/X API v2 Bearer token
      - FLICKR_API_KEY       — Flickr API key for authenticated search
    """

    scanner_name = "social_media_geofence"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        lat, lon, radius_km = self._parse_input(input_value)
        if lat is None or lon is None:
            return self._error_result(input_value, "Invalid coordinate format. Expected 'lat,lon[,radius_km]'.")

        twitter_token = os.getenv("TWITTER_BEARER_TOKEN")
        flickr_key = os.getenv("FLICKR_API_KEY")

        all_posts: list[dict[str, Any]] = []
        platform_coverage: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS) as client:
            # Twitter/X
            if twitter_token:
                twitter_posts = await self._search_twitter(client, lat, lon, radius_km, twitter_token)
                all_posts.extend(twitter_posts)
                platform_coverage["twitter"] = len(twitter_posts)
            else:
                platform_coverage["twitter"] = 0

            # Flickr
            flickr_posts = await self._search_flickr(client, lat, lon, radius_km, flickr_key)
            all_posts.extend(flickr_posts)
            platform_coverage["flickr"] = len(flickr_posts)

        # Always provide manual investigation URLs
        search_urls = {
            "twitter_manual": _build_twitter_manual_url(lat, lon, radius_km),
            "instagram_manual": _build_instagram_manual_url(lat, lon),
            "flickr_manual": _build_flickr_manual_url(lat, lon, radius_km),
            "google_maps_nearby": _build_google_maps_nearby_url(lat, lon),
            "yandex_maps": _build_yandex_maps_url(lat, lon),
        }

        return {
            "input": input_value,
            "found": len(all_posts) > 0,
            "lat": lat,
            "lon": lon,
            "search_radius_km": radius_km,
            "posts_found": all_posts,
            "total_posts": len(all_posts),
            "platform_coverage": platform_coverage,
            "search_urls": search_urls,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [f"coordinates:{lat},{lon}"],
        }

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------

    def _parse_input(self, value: str) -> tuple[float | None, float | None, float]:
        try:
            parts = [p.strip() for p in value.strip().split(",")]
            if len(parts) < 2:
                return None, None, _DEFAULT_RADIUS_KM
            lat = float(parts[0])
            lon = float(parts[1])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None, None, _DEFAULT_RADIUS_KM
            radius_km = float(parts[2]) if len(parts) > 2 else _DEFAULT_RADIUS_KM
            radius_km = min(max(radius_km, 0.1), _MAX_RADIUS_KM)
            return lat, lon, radius_km
        except ValueError:
            return None, None, _DEFAULT_RADIUS_KM

    # ------------------------------------------------------------------
    # Twitter/X API v2
    # ------------------------------------------------------------------

    async def _search_twitter(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lon: float,
        radius_km: float,
        token: str,
    ) -> list[dict[str, Any]]:
        try:
            params = {
                "query": f"point_radius:[{lon} {lat} {radius_km}km] -is:retweet has:geo",
                "max_results": "10",
                "tweet.fields": "created_at,author_id,geo,text",
                "expansions": "author_id",
                "user.fields": "username,name",
            }
            resp = await client.get(
                _TWITTER_SEARCH_URL,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 429:
                log.warning("Twitter rate limited", lat=lat, lon=lon)
                return []
            if resp.status_code != 200:
                log.warning("Twitter API error", status=resp.status_code)
                return []

            data = resp.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            posts: list[dict[str, Any]] = []
            for t in tweets:
                user = users.get(t.get("author_id", ""), {})
                posts.append({
                    "platform": "twitter",
                    "id": t.get("id"),
                    "text": t.get("text", "")[:200],
                    "author_id": t.get("author_id"),
                    "author_username": user.get("username", ""),
                    "created_at": t.get("created_at"),
                    "url": f"https://twitter.com/i/web/status/{t.get('id')}",
                })
            return posts
        except Exception as exc:
            log.warning("Twitter geo search failed", lat=lat, lon=lon, error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Flickr API
    # ------------------------------------------------------------------

    async def _search_flickr(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lon: float,
        radius_km: float,
        api_key: str | None,
    ) -> list[dict[str, Any]]:
        if not api_key:
            # Return empty — manual URL provided in search_urls
            return []
        try:
            params = {
                "method": "flickr.photos.search",
                "api_key": api_key,
                "lat": str(lat),
                "lon": str(lon),
                "radius": str(min(radius_km, 32)),
                "radius_units": "km",
                "extras": "date_taken,owner_name,url_sq,geo,tags",
                "per_page": "20",
                "format": "json",
                "nojsoncallback": "1",
                "sort": "date-posted-desc",
            }
            resp = await client.get(_FLICKR_API_URL, params=params)
            if resp.status_code != 200:
                log.warning("Flickr API error", status=resp.status_code)
                return []
            data = resp.json()
            photos = data.get("photos", {}).get("photo", [])
            posts: list[dict[str, Any]] = []
            for p in photos:
                farm = p.get("farm")
                server = p.get("server")
                photo_id = p.get("id")
                secret = p.get("secret")
                thumb_url = f"https://farm{farm}.staticflickr.com/{server}/{photo_id}_{secret}_s.jpg"
                page_url = f"https://www.flickr.com/photos/{p.get('owner')}/{photo_id}"
                posts.append({
                    "platform": "flickr",
                    "id": photo_id,
                    "title": p.get("title", ""),
                    "owner": p.get("owner"),
                    "owner_name": p.get("ownername", ""),
                    "date_taken": p.get("datetaken"),
                    "tags": p.get("tags", ""),
                    "latitude": p.get("latitude"),
                    "longitude": p.get("longitude"),
                    "thumb_url": thumb_url,
                    "url": page_url,
                })
            return posts
        except Exception as exc:
            log.warning("Flickr geo search failed", lat=lat, lon=lon, error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "posts_found": [],
            "total_posts": 0,
            "platform_coverage": {},
            "search_urls": {},
            "search_radius_km": _DEFAULT_RADIUS_KM,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        identifiers = raw_data.get("extracted_identifiers", [])
        for post in raw_data.get("posts_found", []):
            username = post.get("author_username") or post.get("owner_name")
            if username:
                identifiers.append(f"username:{username}")
        return list(dict.fromkeys(identifiers))
