"""Base class for Playwright-based scrapers with anti-detection measures.

PERFORMANCE NOTE: Currently each scan launches a fresh browser instance (~1-2s overhead).
For production deployments with heavy Playwright usage, implement a browser pool:
- Maintain a persistent browser with `browser = await p.chromium.launch()`
- Create fresh `browser.new_context()` for each scan (isolation without browser restart)
- Use a semaphore to limit concurrent contexts to `MAX_CONCURRENT_BROWSERS`
"""

import asyncio
import random
from abc import abstractmethod
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner

log = structlog.get_logger()

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pl-PL', 'pl', 'en-US', 'en'] });
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""


class PlaywrightBaseScanner(BaseOsintScanner):
    """Base class for Playwright-based web scraping scanners.

    Provides stealth configuration, random delays, and proper
    resource cleanup. Subclasses implement `_scrape_page`.
    """

    async def _do_scan(self, input_value: str, input_type: Any) -> dict[str, Any]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            log.warning("playwright not installed, returning stub")
            return {"_stub": True, "error": "playwright not installed", "extracted_identifiers": []}

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="pl-PL",
                timezone_id="Europe/Warsaw",
                extra_http_headers={
                    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            await context.add_init_script(_STEALTH_SCRIPT)

            try:
                page = await context.new_page()
                return await self._scrape_page(page, input_value, input_type)
            finally:
                await context.close()
                await browser.close()

    @abstractmethod
    async def _scrape_page(self, page: Any, input_value: str, input_type: Any) -> dict[str, Any]:
        """Subclasses implement the actual page interaction here."""
        ...

    @staticmethod
    async def _human_delay(min_sec: float = 1.0, max_sec: float = 3.5) -> None:
        """Random delay to mimic human interaction timing."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
