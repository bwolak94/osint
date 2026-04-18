"""Dark web mentions scanner — checks for mentions on dark web monitoring services."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class DarkWebScanner(BaseOsintScanner):
    scanner_name = "darkweb"
    supported_input_types = frozenset({ScanInputType.EMAIL, ScanInputType.DOMAIN, ScanInputType.USERNAME})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Use ahmia.fi (Tor search engine with clearnet interface) for dark web mentions
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://ahmia.fi/search/",
                    params={"q": input_value},
                    follow_redirects=True,
                )

                if resp.status_code != 200:
                    return {
                        "input": input_value,
                        "found": False,
                        "mention_count": 0,
                        "mentions": [],
                        "extracted_identifiers": [],
                    }

                html = resp.text
                # Count search result entries
                results_count = html.count('class="result"') + html.count('class="search-result"')

                # Also generate intelligence dork queries
                dork_queries = [
                    f'site:*.onion "{input_value}"',
                    f'intext:"{input_value}" site:pastebin.com OR site:ghostbin.com',
                ]

                identifiers: list[str] = []
                if results_count > 0:
                    identifiers.append(f"darkweb_mentions:{results_count}")

                return {
                    "input": input_value,
                    "found": results_count > 0,
                    "mention_count": results_count,
                    "source": "ahmia.fi",
                    "dork_queries": dork_queries,
                    "mentions": [],  # Would be parsed from HTML in production
                    "extracted_identifiers": identifiers,
                }
        except Exception as e:
            log.warning("Dark web search failed, returning dork queries only", error=str(e))
            return {
                "input": input_value,
                "found": False,
                "mention_count": 0,
                "source": "dork_only",
                "dork_queries": [f'site:*.onion "{input_value}"'],
                "mentions": [],
                "extracted_identifiers": [],
            }
