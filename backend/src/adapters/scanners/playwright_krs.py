"""Playwright scanner for KRS (Krajowy Rejestr Sadowy) — Polish company registry."""

import asyncio
import random
from typing import Any

import structlog

from src.adapters.scanners.playwright_base import PlaywrightBaseScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class PlaywrightKRSScanner(PlaywrightBaseScanner):
    """Scrapes ekrs.ms.gov.pl for company registration data.

    Input: NIP or company name.
    Output: board members, beneficial owners, registration history.
    """

    scanner_name = "playwright_krs"
    supported_input_types = frozenset({ScanInputType.NIP, ScanInputType.DOMAIN})
    cache_ttl = 604800  # 7 days — KRS data rarely changes

    async def _scrape_page(self, page: Any, input_value: str, input_type: Any) -> dict[str, Any]:
        await page.goto("https://ekrs.ms.gov.pl/web/wyszukiwarka-krs/strona-glowna/index.html", wait_until="networkidle")
        await self._human_delay(2.0, 4.0)

        # Fill search form based on input type
        if input_type == ScanInputType.NIP:
            await page.click('a:has-text("NIP")', timeout=5000)
            await self._human_delay(0.5, 1.5)
            nip_input = page.locator('input[name="nipInput"], input#nipInput, input[placeholder*="NIP"]').first
            await nip_input.fill(input_value)
        else:
            name_input = page.locator('input[name="nazwaInput"], input#nazwaInput, input[placeholder*="nazwa"]').first
            await name_input.fill(input_value)

        await self._human_delay(0.5, 1.5)

        # Submit search
        submit = page.locator('button[type="submit"], input[type="submit"], button:has-text("Szukaj")').first
        await submit.click()

        try:
            await page.wait_for_selector('.result-row, .search-results, table tbody tr', timeout=15000)
        except Exception:
            return {
                "query": input_value,
                "found": False,
                "results": [],
                "extracted_identifiers": [],
            }

        await self._human_delay()

        # Extract data from results
        results = await page.evaluate("""() => {
            const rows = document.querySelectorAll('.result-row, table tbody tr');
            return Array.from(rows).slice(0, 10).map(row => {
                const cells = row.querySelectorAll('td, .cell');
                return Array.from(cells).map(c => c.textContent.trim());
            });
        }""")

        identifiers: list[str] = []
        for row in results:
            for cell in row:
                if cell:
                    identifiers.append(f"krs_data:{cell}")

        return {
            "query": input_value,
            "found": len(results) > 0,
            "results": results,
            "result_count": len(results),
            "source_url": "https://ekrs.ms.gov.pl",
            "extracted_identifiers": identifiers[:50],
        }
