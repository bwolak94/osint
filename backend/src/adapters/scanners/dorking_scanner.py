"""Google dorking scanner — generates and optionally executes targeted search queries."""

from typing import Any
from urllib.parse import quote_plus

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20

_DORK_TEMPLATES: list[str] = [
    "site:{domain} filetype:pdf",
    "site:{domain} filetype:xls OR filetype:xlsx",
    "site:{domain} inurl:admin OR inurl:login OR inurl:panel",
    'site:{domain} intext:"index of"',
    "site:{domain} ext:env OR ext:config OR ext:conf",
    'site:{domain} inurl:".git"',
    '"@{domain}" email',
    "site:{domain} inurl:api",
    'site:{domain} "phpMyAdmin"',
    'site:{domain} "Powered by" (WordPress OR Joomla OR Drupal)',
    "site:{domain} filetype:sql OR filetype:bak",
    'site:{domain} "DB_PASSWORD" OR "DB_USER" OR "SECRET_KEY"',
    "site:{domain} inurl:swagger OR inurl:openapi",
    'site:{domain} "Error" OR "Exception" OR "Stack trace"',
    "site:{domain} inurl:upload OR inurl:backup",
]


def _build_dorks(domain: str) -> list[str]:
    return [template.format(domain=domain) for template in _DORK_TEMPLATES]


class GoogleDorkScanner(BaseOsintScanner):
    """Generates targeted Google dork queries for a domain.

    When a SerpAPI key is configured the queries are executed and URLs are
    returned. Without a key the scanner returns the dork strings for manual use.

    Configuration note:
        serpapi_api_key (str): Set via SERPAPI_API_KEY env var to enable
            automated execution of dork queries via SerpAPI.
    """

    scanner_name = "google_dorks"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    def __init__(self, serpapi_api_key: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._serpapi_api_key = serpapi_api_key

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        dork_queries = _build_dorks(input_value)
        executed = bool(self._serpapi_api_key)

        results: dict[str, list[str]] = {}
        all_found_urls: list[str] = []

        if executed:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                for dork in dork_queries:
                    urls = await self._execute_dork(client, dork)
                    results[dork] = urls
                    all_found_urls.extend(urls)
        else:
            log.info(
                "SerpAPI key not configured — returning dork queries for manual use",
                domain=input_value,
            )
            results = {dork: [] for dork in dork_queries}

        identifiers = list({f"url:{url}" for url in all_found_urls})

        return {
            "domain": input_value,
            "dork_queries": dork_queries,
            "results": results,
            "executed": executed,
            "total_urls_found": len(all_found_urls),
            "extracted_identifiers": identifiers,
        }

    async def _execute_dork(self, client: httpx.AsyncClient, query: str) -> list[str]:
        """Execute a single dork query via SerpAPI and return the result URLs."""
        url = "https://serpapi.com/search"
        params = {
            "engine": "google",
            "q": query,
            "api_key": self._serpapi_api_key,
            "num": 10,
        }
        try:
            resp = await client.get(url, params=params)

            if resp.status_code == 429:
                raise RateLimitError("SerpAPI rate limited")
            if resp.status_code == 401:
                log.error("SerpAPI authentication failed — check api key")
                return []
            if resp.status_code != 200:
                log.warning("SerpAPI unexpected response", status=resp.status_code, query=query)
                return []

            data = resp.json()
            organic_results: list[dict[str, Any]] = data.get("organic_results", [])
            urls = [r.get("link", "") for r in organic_results if r.get("link")]
            log.debug("Dork executed", query=query, urls_found=len(urls))
            return urls

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("SerpAPI query failed", query=query, error=str(exc))
            return []
