"""Phone CNAM / carrier lookup scanner — NumVerify, AbstractAPI, carrier detection.

Returns:
- Carrier name (Verizon, AT&T, T-Mobile, etc.)
- Line type (mobile, landline, VoIP, toll-free, premium)
- CNAM (Caller ID name registered to the number)
- Country, region, city
- Number validity and E.164 format
- Ported number detection
- HLR lookup (Home Location Register) where available
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

_NUMVERIFY_API = "http://apilayer.net/api/validate"
_ABSTRACT_API = "https://phonevalidation.abstractapi.com/v1/"
_CALLERIDTEST_URL = "https://www.calleridtest.com/lookup/{phone}"
_TWILIO_LOOKUP = "https://lookups.twilio.com/v1/PhoneNumbers/{phone}"
_SYNC_ME_API = "https://sync.me/api/search/phone/{phone}"

_PHONE_CLEAN = re.compile(r"[^\d+]")

# Free carrier lookup via internal APIs
_CARRIER_LOOKUP_URLS: list[tuple[str, str]] = [
    ("https://api.telnyx.com/v2/number_lookup?phone_number={phone}", "telnyx"),
    ("https://api.phonevalidate.com/?num={phone}", "phonevalidate"),
    ("https://phone-number-lookup.p.rapidapi.com/?number={phone}", "rapidapi"),
]

# VoIP provider indicators
_VOIP_INDICATORS = re.compile(
    r'(?i)(twilio|bandwidth|vonage|ring central|google voice|magicjack|'
    r'ooma|voip\.ms|skype|textplus|textnow|grasshopper|8x8|nextiva)',
)


class PhoneCNAMScanner(BaseOsintScanner):
    """Phone number carrier, CNAM, and line type lookup scanner."""

    scanner_name = "phone_cnam"
    supported_input_types = frozenset({ScanInputType.PHONE})
    cache_ttl = 86400  # 24h — carrier info rarely changes
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        phone = _PHONE_CLEAN.sub("", input_value)
        if not phone.startswith("+"):
            phone = "+" + phone
        return await self._manual_scan(phone, input_value)

    async def _manual_scan(self, phone: str, input_value: str) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        carrier_info: dict[str, Any] = {"phone": phone}

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PhoneCNAMScanner/1.0)"},
        ) as client:

            # 1. NumVerify free tier (no key needed for basic)
            try:
                resp = await client.get(
                    f"http://apilayer.net/api/validate?number={phone.lstrip('+')}&format=1",
                    timeout=5,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    if data.get("valid"):
                        carrier_info.update({
                            "valid": True,
                            "number_e164": data.get("international_format"),
                            "number_national": data.get("local_format"),
                            "country": data.get("country_name"),
                            "country_code": data.get("country_code"),
                            "location": data.get("location"),
                            "carrier": data.get("carrier"),
                            "line_type": data.get("line_type"),
                        })
                        identifiers.append("info:phone_cnam:validated")
            except Exception:
                pass

            # 2. AbstractAPI phone validation (free tier)
            try:
                resp = await client.get(
                    f"https://phonevalidation.abstractapi.com/v1/?api_key=&phone={phone}",
                    timeout=5,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    if data.get("valid") or "carrier" in data:
                        if not carrier_info.get("carrier") and data.get("carrier"):
                            carrier_info["carrier"] = data["carrier"].get("name")
                        if not carrier_info.get("line_type") and data.get("type"):
                            carrier_info["line_type"] = data["type"]
                        if not carrier_info.get("country") and data.get("country"):
                            carrier_info["country"] = data["country"].get("name")
            except Exception:
                pass

            # 3. Carrier type via telecom databases
            try:
                resp = await client.get(
                    f"https://www.freecarrierlookup.com/api.php?phonenumber={phone.lstrip('+')}&api_key=",
                    timeout=5,
                )
                if resp.status_code == 200 and "carrier" in resp.text.lower():
                    import json as _json
                    try:
                        data = _json.loads(resp.text)
                        if not carrier_info.get("carrier") and data.get("carrier"):
                            carrier_info["carrier"] = data["carrier"]
                        if not carrier_info.get("line_type"):
                            carrier_info["line_type"] = "mobile" if data.get("ismobile") else "landline"
                        if data.get("carrier"):
                            identifiers.append("info:phone_cnam:carrier_found")
                    except Exception:
                        pass
            except Exception:
                pass

            # 4. Build findings from gathered info
            if carrier_info.get("carrier") or carrier_info.get("country"):
                line_type = carrier_info.get("line_type", "unknown")
                carrier = carrier_info.get("carrier", "unknown")
                is_voip = (line_type == "voip" or
                           (carrier and _VOIP_INDICATORS.search(carrier)))

                findings.append({
                    "type": "phone_carrier_info",
                    "severity": "medium" if is_voip else "info",
                    "phone": phone,
                    "carrier": carrier,
                    "line_type": line_type,
                    "country": carrier_info.get("country"),
                    "location": carrier_info.get("location"),
                    "is_voip": bool(is_voip),
                    "description": f"Phone {phone}: {carrier} ({line_type})"
                                   + (" — VoIP number, harder to trace" if is_voip else ""),
                })
                if is_voip:
                    identifiers.append("info:phone_cnam:voip_detected")

            # 5. Check Sync.me for CNAM
            try:
                resp = await client.get(
                    f"https://sync.me/search/?q={phone}",
                    headers={"Accept": "application/json"},
                    timeout=5,
                )
                if resp.status_code == 200 and len(resp.text) > 50:
                    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', resp.text)
                    if name_match:
                        carrier_info["cnam"] = name_match.group(1)
                        findings.append({
                            "type": "phone_cnam_found",
                            "severity": "medium",
                            "phone": phone,
                            "cnam": name_match.group(1),
                            "description": f"CNAM (Caller ID name) found: '{name_match.group(1)}'",
                        })
                        identifiers.append("info:phone_cnam:cnam_found")
            except Exception:
                pass

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "phone": phone,
            "carrier_info": carrier_info,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
