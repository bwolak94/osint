"""Ignorant scanner — check if a phone number is registered on social platforms."""

import asyncio
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_STATUS_REGISTERED = "registered"
_STATUS_NOT_REGISTERED = "not_registered"
_STATUS_UNKNOWN = "unknown"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"}


class IgnorantScanner(BaseOsintScanner):
    scanner_name = "ignorant"
    supported_input_types = frozenset({ScanInputType.PHONE})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        phone = input_value.strip()
        # Normalise: ensure leading + for international format
        if not phone.startswith("+"):
            phone = f"+{phone}"

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            results = await asyncio.gather(
                self._check_snapchat(client, phone),
                self._check_instagram(client, phone),
                self._check_whatsapp(client, phone),
                self._check_telegram(client, phone),
                return_exceptions=True,
            )

        platforms = ["Snapchat", "Instagram", "WhatsApp", "Telegram"]
        platform_results: dict[str, str] = {}
        for platform, result in zip(platforms, results):
            if isinstance(result, Exception):
                log.debug("Platform check failed", platform=platform, error=str(result))
                platform_results[platform] = _STATUS_UNKNOWN
            else:
                platform_results[platform] = result  # type: ignore[assignment]

        found_count = sum(1 for v in platform_results.values() if v == _STATUS_REGISTERED)

        return {
            "phone": phone,
            "platform_results": platform_results,
            "found_count": found_count,
            "extracted_identifiers": [],
        }

    async def _check_snapchat(self, client: httpx.AsyncClient, phone: str) -> str:
        """Check Snapchat registration via account lookup endpoint."""
        try:
            resp = await client.get(
                f"https://www.snapchat.com/add/{phone.replace('+', '')}",
            )
            # Snapchat returns 200 for valid users; exact behaviour depends on format
            if resp.status_code == 200 and "snapchat" in resp.text.lower():
                return _STATUS_REGISTERED
            if resp.status_code == 404:
                return _STATUS_NOT_REGISTERED
            return _STATUS_UNKNOWN
        except Exception:
            return _STATUS_UNKNOWN

    async def _check_instagram(self, client: httpx.AsyncClient, phone: str) -> str:
        """Probe Instagram account creation endpoint to infer phone registration."""
        try:
            resp = await client.post(
                "https://www.instagram.com/accounts/web_create_ajax/attempt/",
                data={"phone_number": phone},
                headers={**_HEADERS, "X-CSRFToken": "missing", "Referer": "https://www.instagram.com/"},
            )
            body: dict[str, Any] = {}
            try:
                body = resp.json()
            except Exception:
                pass
            errors = body.get("errors", {})
            if "phone_number" in errors:
                # Error about phone_number existing implies it's already registered
                msgs = errors["phone_number"]
                if any("already" in str(m).lower() or "registered" in str(m).lower() for m in msgs):
                    return _STATUS_REGISTERED
            if resp.status_code in (200, 400):
                return _STATUS_UNKNOWN
            return _STATUS_UNKNOWN
        except Exception:
            return _STATUS_UNKNOWN

    async def _check_whatsapp(self, client: httpx.AsyncClient, phone: str) -> str:
        """Probe WhatsApp click-to-chat to infer number validity."""
        try:
            # WhatsApp click-to-chat redirects to app; 302 often indicates valid number
            digits = phone.replace("+", "").replace(" ", "").replace("-", "")
            resp = await client.head(f"https://api.whatsapp.com/send?phone={digits}")
            if resp.status_code in (200, 302):
                return _STATUS_UNKNOWN  # Can't distinguish registered vs. not without app
            return _STATUS_UNKNOWN
        except Exception:
            return _STATUS_UNKNOWN

    async def _check_telegram(self, client: httpx.AsyncClient, phone: str) -> str:
        """Check Telegram by probing the t.me deep link for the phone number."""
        try:
            digits = phone.replace("+", "").replace(" ", "").replace("-", "")
            resp = await client.get(f"https://t.me/+{digits}")
            if resp.status_code == 200 and "tgme_page_title" in resp.text:
                return _STATUS_REGISTERED
            if resp.status_code in (302, 404):
                return _STATUS_NOT_REGISTERED
            return _STATUS_UNKNOWN
        except Exception:
            return _STATUS_UNKNOWN

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
