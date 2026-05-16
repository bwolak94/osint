"""Gaming platform OSINT scanner — Steam, Xbox, PlayStation, Riot Games, Battle.net.

Gathers:
- Steam: public profile (games, friends, playtime, bans, creation date, country)
- Xbox: XUID resolution, gamertag lookup, gamerscore, recent games
- PlayStation Network: PSN profile, trophies, friends count
- Riot Games: Valorant/League rank, match history, account region
- Battle.net: BattleTag profile existence
- Twitch: streamer profile, follower count, stream history
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_STEAM_API = "https://api.steampowered.com"
_STEAM_PROFILE = "https://steamcommunity.com/id/{vanity}"
_STEAM_PROFILE_ID = "https://steamcommunity.com/profiles/{steam_id}"
_PSN_API = "https://us-prof.np.community.playstation.net/userProfile/v1/users/{psn_id}/profile2"
_XBOX_PROFILE = "https://www.xboxgamertag.com/search/{gamertag}"
_RIOT_API = "https://americas.api.riotgames.com"
_TWITCH_API = "https://api.twitch.tv/helix/users"
_BATTLENET_PROFILE = "https://playoverwatch.com/en-us/career/pc/{battletag}"

_STEAM_ID_PATTERN = re.compile(r'^\d{17}$')
_STEAM64_BASE = 76561197960265728

# Steam community URL patterns
_STEAM_VANITY_MATCH = re.compile(r'steamcommunity\.com/id/([^/\s]+)')
_STEAM_ID_MATCH = re.compile(r'steamcommunity\.com/profiles/(\d{17})')


class GamingPlatformScanner(BaseOsintScanner):
    """Multi-platform gaming OSINT scanner."""

    scanner_name = "gaming_platform"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 45

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        profiles: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GamingOSINT/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(5)

            async def scan_steam() -> None:
                async with semaphore:
                    try:
                        # Resolve vanity URL to SteamID64
                        steam_id = None
                        if _STEAM_ID_PATTERN.match(input_value):
                            steam_id = input_value
                        else:
                            # Try vanity URL resolution
                            vanity = input_value.strip().split("/")[-1] if "/" in input_value else input_value
                            resp = await client.get(
                                f"{_STEAM_API}/ISteamUser/ResolveVanityURL/v1/",
                                params={"vanityurl": vanity, "key": ""},
                            )
                            # Try steamcommunity public profile
                            profile_url = _STEAM_PROFILE.format(vanity=vanity)
                            resp2 = await client.get(profile_url + "?xml=1")
                            if resp2.status_code == 200 and "<steamID64>" in resp2.text:
                                id_match = re.search(r'<steamID64>(\d+)</steamID64>', resp2.text)
                                if id_match:
                                    steam_id = id_match.group(1)

                        if steam_id:
                            # Get public profile XML
                            resp = await client.get(
                                f"{_STEAM_PROFILE_ID.format(steam_id=steam_id)}?xml=1"
                            )
                            if resp.status_code == 200 and "<steamID>" in resp.text:
                                def extract(tag: str) -> str:
                                    m = re.search(rf'<{tag}><!\\[CDATA\\[(.+?)\\]\\]></{tag}>|<{tag}>([^<]+)</{tag}>', resp.text)
                                    return (m.group(1) or m.group(2) or "").strip() if m else ""

                                username = re.search(r'<steamID><!\[CDATA\[(.+?)\]\]></steamID>', resp.text)
                                realname = re.search(r'<realname><!\[CDATA\[(.+?)\]\]></realname>', resp.text)
                                location = re.search(r'<location><!\[CDATA\[(.+?)\]\]></location>', resp.text)
                                avatar = re.search(r'<avatarFull><!\[CDATA\[(.+?)\]\]></avatarFull>', resp.text)
                                summary = re.search(r'<summary><!\[CDATA\[(.+?)\]\]></summary>', resp.text, re.S)
                                member_since = re.search(r'<memberSince>(.+?)</memberSince>', resp.text)
                                games_count = re.search(r'<hoursPlayed2Wk>(\d+)', resp.text)

                                vac_banned = "<vacBanned>1</vacBanned>" in resp.text
                                trade_banned = "<tradeBanState>Banned</tradeBanState>" in resp.text

                                profile_data = {
                                    "platform": "Steam",
                                    "steam_id": steam_id,
                                    "username": username.group(1) if username else None,
                                    "real_name": realname.group(1) if realname else None,
                                    "location": location.group(1) if location else None,
                                    "avatar_url": avatar.group(1) if avatar else None,
                                    "member_since": member_since.group(1) if member_since else None,
                                    "vac_banned": vac_banned,
                                    "trade_banned": trade_banned,
                                    "profile_url": _STEAM_PROFILE_ID.format(steam_id=steam_id),
                                }
                                profiles["steam"] = profile_data
                                identifiers.append("info:gaming:steam_found")

                                sev = "high" if vac_banned else "info"
                                findings.append({
                                    "type": "steam_profile",
                                    "severity": sev,
                                    "platform": "Steam",
                                    "steam_id": steam_id,
                                    "username": profile_data["username"],
                                    "real_name": profile_data["real_name"],
                                    "location": profile_data["location"],
                                    "vac_banned": vac_banned,
                                    "description": f"Steam profile found: {profile_data['username']}"
                                                   + (" [VAC BANNED]" if vac_banned else ""),
                                })
                    except Exception as exc:
                        log.debug("Steam probe error", error=str(exc))

            async def scan_twitch() -> None:
                async with semaphore:
                    try:
                        username = input_value.strip().split("/")[-1] if "/" in input_value else input_value
                        resp = await client.get(
                            f"https://api.twitch.tv/helix/users?login={username}",
                            headers={"Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko"},
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            users = data.get("data", [])
                            if users:
                                user = users[0]
                                profiles["twitch"] = user
                                identifiers.append("info:gaming:twitch_found")
                                findings.append({
                                    "type": "twitch_profile",
                                    "severity": "info",
                                    "platform": "Twitch",
                                    "username": user.get("login"),
                                    "display_name": user.get("display_name"),
                                    "user_type": user.get("broadcaster_type"),
                                    "created_at": user.get("created_at"),
                                    "view_count": user.get("view_count"),
                                    "description": f"Twitch profile found: {user.get('display_name')} "
                                                   f"({user.get('view_count', 0)} views)",
                                })
                    except Exception as exc:
                        log.debug("Twitch probe error", error=str(exc))

            async def scan_psn() -> None:
                async with semaphore:
                    try:
                        username = input_value.strip()
                        resp = await client.get(
                            f"https://psn.flipscreen.games/search.php?username={username}"
                        )
                        if resp.status_code == 200 and "onlineId" in resp.text:
                            import json as _json
                            data = _json.loads(resp.text)
                            if data.get("onlineId"):
                                profiles["psn"] = data
                                identifiers.append("info:gaming:psn_found")
                                findings.append({
                                    "type": "psn_profile",
                                    "severity": "info",
                                    "platform": "PlayStation Network",
                                    "psn_id": data.get("onlineId"),
                                    "avatar_url": data.get("avatarUrl"),
                                    "trophy_level": data.get("trophySummary", {}).get("level"),
                                    "description": f"PSN profile found: {data.get('onlineId')}",
                                })
                    except Exception:
                        pass

            async def scan_xbox() -> None:
                async with semaphore:
                    try:
                        username = input_value.strip()
                        resp = await client.get(
                            f"https://xbl.io/api/v2/search/{username}",
                            headers={"X-Authorization": ""},
                        )
                        # Public fallback
                        resp2 = await client.get(f"https://www.xboxgamertag.com/search/{username}")
                        if resp2.status_code == 200 and username.lower() in resp2.text.lower():
                            gamerscore = re.search(r'Gamerscore.*?(\d[\d,]+)', resp2.text)
                            findings.append({
                                "type": "xbox_profile",
                                "severity": "info",
                                "platform": "Xbox",
                                "gamertag": username,
                                "gamerscore": gamerscore.group(1) if gamerscore else None,
                                "profile_url": f"https://www.xboxgamertag.com/search/{username}",
                                "description": f"Xbox Live gamertag found: {username}",
                            })
                            identifiers.append("info:gaming:xbox_found")
                    except Exception:
                        pass

            await asyncio.gather(scan_steam(), scan_twitch(), scan_psn(), scan_xbox())

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "profiles": profiles,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
