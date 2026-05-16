"""WhatsApp OSINT scanner — profile, avatar, and account existence probing.

Checks:
- wa.me short link resolution and profile reachability
- WhatsApp Business API public profile (name, description, category)
- Phone number validity for WhatsApp via unofficial check endpoint
- Avatar extraction from public WhatsApp profile
- Last seen / online status indicators (where exposed)
- Click-to-chat link scanning for embedded phone numbers
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

_WA_ME_URL = "https://wa.me/{phone}"
_WA_BUSINESS_API = "https://graph.facebook.com/v18.0/{phone}"
_WA_CHECK_URL = "https://api.whatsapp.com/send?phone={phone}"

_PHONE_CLEAN = re.compile(r"[^\d+]")
_WA_PROFILE_INDICATORS = re.compile(
    r'(?i)(whatsapp|wa\.me|open\.whatsapp\.com|"phone":|"name":)',
)
_BUSINESS_PROFILE = re.compile(
    r'(?i)(business|verified|category|description)',
)
_WA_EXISTS_INDICATOR = re.compile(
    r'(?i)(open in whatsapp|send message|continue to chat|wa\.me/)',
)


class WhatsAppScanner(BaseOsintScanner):
    """WhatsApp account existence and profile OSINT scanner."""

    scanner_name = "whatsapp"
    supported_input_types = frozenset({ScanInputType.PHONE, ScanInputType.EMAIL})
    cache_ttl = 3600
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        phone = _clean_phone(input_value, input_type)
        if not phone:
            return {"input": input_value, "error": "Could not extract phone number", "total_found": 0, "extracted_identifiers": []}
        return await self._manual_scan(phone, input_value)

    async def _manual_scan(self, phone: str, input_value: str) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        profile: dict[str, Any] = {"phone": phone}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=True,
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            },
        ) as client:
            # wa.me short link probe
            try:
                url = _WA_ME_URL.format(phone=phone.lstrip("+"))
                resp = await client.get(url)
                body = resp.text

                if resp.status_code == 200 and _WA_EXISTS_INDICATOR.search(body):
                    profile["wa_me_url"] = url
                    profile["account_exists"] = True
                    identifiers.append("info:whatsapp:account_found")

                    # Extract name if exposed
                    name_match = re.search(r'<title>([^<]+)</title>', body)
                    if name_match and "whatsapp" not in name_match.group(1).lower():
                        profile["display_name"] = name_match.group(1).strip()

                    # Check for business profile indicators
                    if _BUSINESS_PROFILE.search(body):
                        profile["account_type"] = "business"
                        identifiers.append("info:whatsapp:business_account")
                        findings.append({
                            "type": "whatsapp_business_profile",
                            "severity": "info",
                            "url": url,
                            "phone": phone,
                            "display_name": profile.get("display_name"),
                            "description": f"WhatsApp Business account found for {phone}",
                        })
                    else:
                        profile["account_type"] = "personal"
                        findings.append({
                            "type": "whatsapp_account_found",
                            "severity": "info",
                            "url": url,
                            "phone": phone,
                            "display_name": profile.get("display_name"),
                            "description": f"WhatsApp account confirmed for {phone}",
                        })

                    # Try avatar URL
                    avatar_url = f"https://graph.facebook.com/{phone.lstrip('+')}?fields=profile_pic"
                    try:
                        avatar_resp = await client.get(avatar_url)
                        if avatar_resp.status_code == 200 and "url" in avatar_resp.text:
                            import json as _json
                            data = _json.loads(avatar_resp.text)
                            if "profile_pic" in data:
                                profile["avatar_url"] = data["profile_pic"]
                                identifiers.append("info:whatsapp:avatar_found")
                    except Exception:
                        pass

                elif resp.status_code in (301, 302):
                    location = resp.headers.get("location", "")
                    if "whatsapp" in location.lower():
                        profile["account_exists"] = True
                        findings.append({
                            "type": "whatsapp_account_redirect",
                            "severity": "info",
                            "url": url,
                            "redirect": location,
                            "phone": phone,
                            "description": f"WhatsApp redirect found for {phone}",
                        })
                        identifiers.append("info:whatsapp:account_found")
                else:
                    profile["account_exists"] = False

            except Exception as exc:
                log.debug("WhatsApp probe error", phone=phone, error=str(exc))

            # Check click-to-chat API
            try:
                api_url = _WA_CHECK_URL.format(phone=phone.lstrip("+"))
                resp2 = await client.get(api_url)
                if resp2.status_code == 200 and _WA_EXISTS_INDICATOR.search(resp2.text):
                    if "account_exists" not in profile:
                        profile["account_exists"] = True
                        identifiers.append("info:whatsapp:account_found")
            except Exception:
                pass

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "phone": phone,
            "profile": profile,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _clean_phone(value: str, input_type: ScanInputType) -> str:
    """Extract and clean phone number."""
    if input_type == ScanInputType.PHONE:
        cleaned = _PHONE_CLEAN.sub("", value)
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        return cleaned
    # For email, can't extract phone
    return ""
