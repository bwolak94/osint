"""Skype profile OSINT scanner.

Finds:
- Skype username existence check (skype.com public profile)
- Display name and location from public profile
- Associated Microsoft account indicators
- Skype ID from email via Skype API (unauthenticated public endpoint)
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class SkypeScanner(BaseOsintScanner):
    """Skype profile and account OSINT scanner."""

    scanner_name = "skype"
    supported_input_types = frozenset({ScanInputType.EMAIL, ScanInputType.USERNAME})
    cache_ttl = 86400
    scan_timeout = 20

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        profile: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        ) as client:
            username = query.split("@")[0] if "@" in query else query

            # 1. Skype public profile page
            try:
                resp = await client.get(
                    f"https://www.skype.com/en/search/results/people/?q={quote(username)}",
                    timeout=8,
                )
                if resp.status_code == 200:
                    body = resp.text
                    # Look for profile data
                    name_match = re.search(r'"displayName"\s*:\s*"([^"]+)"', body)
                    skype_id_match = re.search(r'"skypeId"\s*:\s*"([^"]+)"', body)
                    if name_match or skype_id_match:
                        identifiers.append("info:skype:profile_found")
                        profile = {
                            "display_name": name_match.group(1) if name_match else None,
                            "skype_id": skype_id_match.group(1) if skype_id_match else username,
                        }
                        findings.append({
                            "type": "skype_profile_found",
                            "severity": "info",
                            "source": "Skype",
                            "display_name": profile.get("display_name"),
                            "skype_id": profile.get("skype_id"),
                            "url": f"https://join.skype.com/profile/{username}",
                            "description": f"Skype profile found for '{username}'",
                        })
            except Exception as exc:
                log.debug("Skype profile error", error=str(exc))

            # 2. Skype ID reverse lookup via public API
            try:
                resp = await client.get(
                    f"https://api.skype.com/users/self/contacts/profiles?usernames={quote(username)}",
                    timeout=8,
                )
                if resp.status_code in (200, 401, 403):
                    # Even 401 confirms the endpoint exists (username may be valid)
                    if resp.status_code == 200:
                        import json as _json
                        try:
                            data = _json.loads(resp.text)
                            if isinstance(data, list) and data:
                                p = data[0]
                                identifiers.append("info:skype:api_profile_found")
                                findings.append({
                                    "type": "skype_api_profile",
                                    "severity": "info",
                                    "source": "Skype API",
                                    "display_name": p.get("displayname"),
                                    "mood": p.get("mood"),
                                    "city": p.get("city"),
                                    "country": p.get("country"),
                                    "description": f"Skype API: profile data for '{username}'",
                                })
                        except Exception:
                            pass
            except Exception as exc:
                log.debug("Skype API error", error=str(exc))

            # 3. Email → Skype account lookup (Microsoft account)
            if "@" in query:
                try:
                    resp = await client.post(
                        "https://login.live.com/GetCredentialType.srf",
                        json={"username": query, "isOtherIdpSupported": True},
                        headers={"Content-Type": "application/json"},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        import json as _json
                        data = _json.loads(resp.text)
                        if data.get("IfExistsResult") == 0:
                            identifiers.append("info:skype:microsoft_account_exists")
                            findings.append({
                                "type": "microsoft_account_exists",
                                "severity": "info",
                                "source": "Microsoft Login",
                                "email": query,
                                "description": f"Microsoft account (Skype-linked) exists for '{query}'",
                            })
                except Exception as exc:
                    log.debug("Microsoft account check error", error=str(exc))

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "profile": profile,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
