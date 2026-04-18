"""Telegram scanner — public channel/user information lookup."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class TelegramScanner(BaseOsintScanner):
    scanner_name = "telegram"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 21600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.lstrip("@")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://t.me/{username}", follow_redirects=True)
            if resp.status_code == 404:
                return {"username": username, "found": False, "extracted_identifiers": []}

            html = resp.text
            found = "tgme_page_title" in html or "tgme_channel_info" in html

            title = ""
            if 'class="tgme_page_title"' in html:
                start = html.find('class="tgme_page_title"')
                tag_start = html.find(">", start) + 1
                tag_end = html.find("<", tag_start)
                if tag_start > 0 and tag_end > tag_start:
                    title = html[tag_start:tag_end].strip()

            description = ""
            if 'class="tgme_page_description"' in html:
                start = html.find('class="tgme_page_description"')
                tag_start = html.find(">", start) + 1
                tag_end = html.find("<", tag_start)
                if tag_start > 0 and tag_end > tag_start:
                    description = html[tag_start:tag_end].strip()

            identifiers = [f"username:{username}"]
            if found:
                identifiers.append("service:telegram")
                identifiers.append(f"url:https://t.me/{username}")

            return {
                "username": username,
                "found": found,
                "title": title,
                "description": description,
                "url": f"https://t.me/{username}",
                "extracted_identifiers": identifiers,
            }
