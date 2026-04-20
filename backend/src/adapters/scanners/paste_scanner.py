"""Paste sites OSINT scanner — searches pastebin dump databases for leaked data."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_GOOGLE_DORK_SITES = "site:pastebin.com OR site:ghostbin.com OR site:paste.ee"


class PasteSitesScanner(BaseOsintScanner):
    """Searches paste-dump databases for occurrences of an email or username.

    Primary source: psbdmp.ws API (free pastebin dump search engine).
    Also generates a Google dork query for manual follow-up.
    """

    scanner_name = "paste_sites"
    supported_input_types = frozenset({ScanInputType.EMAIL, ScanInputType.USERNAME})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        google_dork = f'{_GOOGLE_DORK_SITES} "{input_value}"'

        pastes = await self._search_psbdmp(input_value)

        if pastes is None:
            # API request failed; return dork-only result
            return {
                "input": input_value,
                "found": False,
                "paste_count": 0,
                "pastes": [],
                "google_dork": google_dork,
                "extracted_identifiers": [],
            }

        identifiers: list[str] = [f"paste:{p['id']}" for p in pastes]

        return {
            "input": input_value,
            "found": len(pastes) > 0,
            "paste_count": len(pastes),
            "pastes": pastes,
            "google_dork": google_dork,
            "extracted_identifiers": identifiers,
        }

    async def _search_psbdmp(self, query: str) -> list[dict[str, Any]] | None:
        """Query the psbdmp.ws API. Returns a list of paste dicts or None on failure."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"https://psbdmp.ws/api/v3/search/{query}")

                if resp.status_code == 404:
                    return []

                resp.raise_for_status()
                data = resp.json()

            if isinstance(data, list):
                return [
                    {
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "date": item.get("time", ""),
                        "source": "psbdmp",
                    }
                    for item in data
                ]

            return []

        except Exception as exc:
            log.warning("psbdmp search failed", query=query, error=str(exc))
            return None
