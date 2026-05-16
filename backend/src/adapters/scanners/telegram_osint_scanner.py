"""Telegram channel/username OSINT scanner.

Uses public Telegram preview endpoints and aggregator indexes to find:
- Public channel metadata (title, description, subscriber count)
- Username existence on t.me
- Channel mentions on public Telegram indexes (tgstat, telemetr)
- Recent public posts preview
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

_SUBSCRIBER_RE = re.compile(r'(?i)(\d[\d\s,\.]+)\s*(?:subscriber|member|follower)')
_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.I)
_DESC_RE = re.compile(r'<meta\s+property="og:description"\s+content="([^"]+)"', re.I)


class TelegramOsintScanner(BaseOsintScanner):
    """Telegram channel and username OSINT scanner."""

    scanner_name = "telegram_osint"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.DOMAIN,
                                        ScanInputType.EMAIL})
    cache_ttl = 3600
    scan_timeout = 25

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        # Normalize: strip @, extract username portion from email
        username = query.lstrip("@")
        if "@" in username:
            username = username.split("@")[0]
        # Remove domain extension if passed a domain
        if "." in username:
            username = username.split(".")[0]

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            semaphore = asyncio.Semaphore(3)

            # 1. Telegram public preview
            async def check_telegram_preview() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://t.me/{username}",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            title_m = _TITLE_RE.search(body)
                            desc_m = _DESC_RE.search(body)
                            sub_m = _SUBSCRIBER_RE.search(body)

                            title = title_m.group(1) if title_m else ""
                            desc = desc_m.group(1) if desc_m else ""
                            subs_raw = sub_m.group(1).replace(",", "").replace(" ", "").replace(".", "") if sub_m else None
                            subscribers = int(subs_raw) if subs_raw and subs_raw.isdigit() else None

                            # Check for actual channel (not 404 page)
                            is_real = bool(title and "Telegram" not in title and username.lower() in body.lower())
                            if is_real or subscribers:
                                identifiers.append("medium:telegram:profile_found")
                                findings.append({
                                    "type": "telegram_profile",
                                    "severity": "medium",
                                    "source": "Telegram t.me",
                                    "username": username,
                                    "title": title,
                                    "description_text": desc[:200] if desc else "",
                                    "subscribers": subscribers,
                                    "url": f"https://t.me/{username}",
                                    "description": f"Telegram @{username}: '{title}'"
                                                   + (f" — {subscribers:,} subscribers" if subscribers else ""),
                                })
                    except Exception as exc:
                        log.debug("Telegram preview error", error=str(exc))

            # 2. TGStat.ru public stats
            async def check_tgstat() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://tgstat.ru/channel/@{username}",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            if username.lower() in body.lower():
                                sub_m = re.search(r'(\d[\d\s,]+)\s*(?:subscriber|участник)', body, re.I)
                                subs = int(sub_m.group(1).replace(",", "").replace(" ", "")) if sub_m else None
                                post_m = re.search(r'(\d+)\s*post', body, re.I)
                                posts = int(post_m.group(1)) if post_m else None
                                if subs or posts:
                                    identifiers.append("info:telegram:tgstat_found")
                                    findings.append({
                                        "type": "telegram_stats",
                                        "severity": "info",
                                        "source": "TGStat",
                                        "username": username,
                                        "subscribers": subs,
                                        "total_posts": posts,
                                        "url": f"https://tgstat.ru/channel/@{username}",
                                        "description": f"TGStat @{username}: {subs or '?'} subscribers, {posts or '?'} posts",
                                    })
                    except Exception as exc:
                        log.debug("TGStat error", error=str(exc))

            # 3. Telemetr.io
            async def check_telemetr() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://telemetr.io/en/channels/{username}",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            if username.lower() in body.lower() and "not found" not in body.lower():
                                sub_m = re.search(r'(\d[\d,]+)\s*(?:subscriber|member)', body, re.I)
                                subs = int(sub_m.group(1).replace(",", "")) if sub_m else None
                                identifiers.append("info:telegram:telemetr_found")
                                findings.append({
                                    "type": "telegram_telemetr",
                                    "severity": "info",
                                    "source": "Telemetr.io",
                                    "username": username,
                                    "subscribers": subs,
                                    "url": f"https://telemetr.io/en/channels/{username}",
                                    "description": f"Telemetr @{username}" + (f": {subs:,} subscribers" if subs else ""),
                                })
                    except Exception as exc:
                        log.debug("Telemetr error", error=str(exc))

            await asyncio.gather(
                check_telegram_preview(),
                check_tgstat(),
                check_telemetr(),
            )

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "username": username,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
