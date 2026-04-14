"""Playwright scanner for CEIDG — Polish sole proprietorship registry."""

from typing import Any

import structlog

from src.adapters.scanners.playwright_base import PlaywrightBaseScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class PlaywrightCEIDGScanner(PlaywrightBaseScanner):
    """Scrapes ceidg.gov.pl for sole proprietorship data."""

    scanner_name = "playwright_ceidg"
    supported_input_types = frozenset({ScanInputType.NIP})

    async def _scrape_page(self, page: Any, input_value: str, input_type: Any) -> dict[str, Any]:
        await page.goto("https://aplikacja.ceidg.gov.pl/ceidg/ceidg.public.ui/Search.aspx", wait_until="networkidle")
        await self._human_delay(2.0, 4.0)

        nip_input = page.locator('input[id*="NIP"], input[name*="NIP"]').first
        await nip_input.fill(input_value)
        await self._human_delay(0.5, 1.5)

        submit = page.locator('input[type="submit"][value*="Szukaj"], button:has-text("Szukaj")').first
        await submit.click()

        try:
            await page.wait_for_selector('.result, .search-results, #results', timeout=15000)
        except Exception:
            return {"query": input_value, "found": False, "results": [], "extracted_identifiers": []}

        content = await page.content()
        return {
            "query": input_value,
            "found": True,
            "source_url": "https://ceidg.gov.pl",
            "page_length": len(content),
            "extracted_identifiers": [],
        }
