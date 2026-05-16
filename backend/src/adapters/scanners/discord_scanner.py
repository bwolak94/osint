"""Discord OSINT scanner — user lookup, server enumeration, invite analysis.

Detects:
- User profile via Discord public API (snowflake ID → username, avatar, badges, creation date)
- Invite link analysis (server name, member count, verification level)
- Username search across known public Discord lookup services
- Webhook exposure detection
- Bot token exposure in public repos (combined with secret scanning)
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_DISCORD_API = "https://discord.com/api/v10"
_DISCORD_CDN = "https://cdn.discordapp.com"

# Discord epoch (2015-01-01T00:00:00Z in milliseconds)
_DISCORD_EPOCH = 1420070400000

_SNOWFLAKE_PATTERN = re.compile(r'^\d{17,19}$')
_INVITE_PATTERN = re.compile(r'discord(?:\.gg|app\.com/invite|\.com/invite)/([A-Za-z0-9\-]+)')
_WEBHOOK_PATTERN = re.compile(
    r'discord(?:app)?\.com/api/webhooks/(\d{17,19})/([A-Za-z0-9_\-]+)'
)

# Badge flags
_FLAGS: dict[int, str] = {
    1 << 0: "Discord Staff",
    1 << 1: "Discord Partner",
    1 << 2: "HypeSquad Events",
    1 << 3: "Bug Hunter Level 1",
    1 << 6: "HypeSquad Bravery",
    1 << 7: "HypeSquad Brilliance",
    1 << 8: "HypeSquad Balance",
    1 << 9: "Early Supporter",
    1 << 14: "Bug Hunter Level 2",
    1 << 17: "Verified Bot Developer",
    1 << 18: "Discord Certified Moderator",
    1 << 19: "Bot HTTP Interactions",
    1 << 22: "Active Developer",
}


def _snowflake_to_datetime(snowflake: int) -> str:
    """Convert Discord snowflake to creation datetime."""
    timestamp_ms = (snowflake >> 22) + _DISCORD_EPOCH
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return dt.isoformat()


def _parse_flags(flags: int) -> list[str]:
    return [name for bit, name in _FLAGS.items() if flags & bit]


class DiscordScanner(BaseOsintScanner):
    """Discord user and server OSINT scanner."""

    scanner_name = "discord"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        profiles: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DiscordScanner/1.0)"},
        ) as client:

            # Case 1: Input is a snowflake ID
            if _SNOWFLAKE_PATTERN.match(input_value.strip()):
                result = await self._lookup_user(client, input_value.strip())
                if result:
                    profiles.append(result)
                    identifiers.append("info:discord:user_found")
                    findings.append({
                        "type": "discord_user_profile",
                        "severity": "info",
                        "user_id": input_value.strip(),
                        "username": result.get("username"),
                        "global_name": result.get("global_name"),
                        "created_at": result.get("created_at"),
                        "badges": result.get("badges", []),
                        "avatar_url": result.get("avatar_url"),
                        "description": f"Discord user found: {result.get('username')} (ID: {input_value.strip()})",
                    })

            # Case 2: URL containing invite or webhook
            invite_matches = _INVITE_PATTERN.findall(input_value)
            for invite_code in invite_matches[:3]:
                result = await self._lookup_invite(client, invite_code)
                if result:
                    findings.append({
                        "type": "discord_invite_info",
                        "severity": "info",
                        "invite_code": invite_code,
                        "server_name": result.get("guild_name"),
                        "member_count": result.get("member_count"),
                        "online_count": result.get("presence_count"),
                        "verification_level": result.get("verification_level"),
                        "description": f"Discord server via invite: {result.get('guild_name')} "
                                       f"({result.get('member_count')} members)",
                    })
                    identifiers.append("info:discord:server_found")

            webhook_matches = _WEBHOOK_PATTERN.findall(input_value)
            for wh_id, wh_token in webhook_matches[:3]:
                result = await self._lookup_webhook(client, wh_id, wh_token)
                if result:
                    findings.append({
                        "type": "discord_webhook_exposed",
                        "severity": "high",
                        "webhook_id": wh_id,
                        "webhook_name": result.get("name"),
                        "channel_id": result.get("channel_id"),
                        "guild_id": result.get("guild_id"),
                        "description": f"Discord webhook exposed — can send messages as '{result.get('name')}'",
                        "remediation": "Delete and regenerate webhook; never expose webhook URLs publicly",
                    })
                    identifiers.append("vuln:discord:webhook_exposed")

            # Case 3: Username lookup via public lookup services
            if input_type == ScanInputType.USERNAME and not _SNOWFLAKE_PATTERN.match(input_value):
                username_result = await self._lookup_by_username(client, input_value)
                if username_result:
                    findings.extend(username_result)
                    identifiers.append("info:discord:username_search")

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "profiles": profiles,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    async def _lookup_user(self, client: httpx.AsyncClient, user_id: str) -> dict[str, Any] | None:
        """Lookup Discord user by snowflake ID."""
        try:
            # Public endpoint — no auth needed for basic profile
            resp = await client.get(f"{_DISCORD_API}/users/{user_id}",
                                    headers={"Authorization": "Bot "})
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                user_id_int = int(user_id)
                created_at = _snowflake_to_datetime(user_id_int)
                avatar_hash = data.get("avatar")
                avatar_url = (f"{_DISCORD_CDN}/avatars/{user_id}/{avatar_hash}.png"
                              if avatar_hash else None)
                flags = data.get("public_flags", 0)
                return {
                    "user_id": user_id,
                    "username": data.get("username"),
                    "global_name": data.get("global_name"),
                    "discriminator": data.get("discriminator"),
                    "avatar_url": avatar_url,
                    "banner_color": data.get("banner_color"),
                    "badges": _parse_flags(flags),
                    "created_at": created_at,
                    "bot": data.get("bot", False),
                }
        except Exception:
            pass

        # Fallback: use public lookup without auth
        try:
            resp = await client.get(f"https://discord.id/api/id/{user_id}")
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                if data.get("success"):
                    user_id_int = int(user_id)
                    return {
                        "user_id": user_id,
                        "username": data.get("username"),
                        "created_at": _snowflake_to_datetime(user_id_int),
                        "source": "discord.id",
                    }
        except Exception:
            pass
        return None

    async def _lookup_invite(self, client: httpx.AsyncClient, code: str) -> dict[str, Any] | None:
        try:
            resp = await client.get(
                f"{_DISCORD_API}/invites/{code}?with_counts=true&with_expiration=true"
            )
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                guild = data.get("guild", {})
                return {
                    "guild_id": guild.get("id"),
                    "guild_name": guild.get("name"),
                    "guild_description": guild.get("description"),
                    "member_count": data.get("approximate_member_count"),
                    "presence_count": data.get("approximate_presence_count"),
                    "verification_level": guild.get("verification_level"),
                    "nsfw": guild.get("nsfw", False),
                    "invite_expires": data.get("expires_at"),
                }
        except Exception:
            pass
        return None

    async def _lookup_webhook(self, client: httpx.AsyncClient, wh_id: str, wh_token: str) -> dict[str, Any] | None:
        try:
            resp = await client.get(f"{_DISCORD_API}/webhooks/{wh_id}/{wh_token}")
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                return {
                    "name": data.get("name"),
                    "channel_id": data.get("channel_id"),
                    "guild_id": data.get("guild_id"),
                    "application_id": data.get("application_id"),
                }
        except Exception:
            pass
        return None

    async def _lookup_by_username(self, client: httpx.AsyncClient, username: str) -> list[dict[str, Any]]:
        results = []
        try:
            resp = await client.get(
                f"https://discord.id/api/name/{username}",
                timeout=5,
            )
            if resp.status_code == 200:
                import json as _json
                data = _json.loads(resp.text)
                if isinstance(data, list):
                    for user in data[:5]:
                        results.append({
                            "type": "discord_username_match",
                            "severity": "info",
                            "username": user.get("username"),
                            "user_id": user.get("id"),
                            "description": f"Discord username match: {user.get('username')}",
                        })
        except Exception:
            pass
        return results

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
