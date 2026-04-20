"""LinkedIn scanner — checks for LinkedIn profile existence and public data."""

from typing import Any
import structlog
from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class LinkedInScanner(BaseOsintScanner):
    """Searches LinkedIn for profiles matching a username or email.

    Uses Google search dorks to find LinkedIn profiles since LinkedIn
    blocks direct scraping. Returns profile URLs and metadata.
    """

    scanner_name = "linkedin"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            profiles: list[dict[str, Any]] = []
            identifiers: list[str] = []

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                # Method 1: Direct LinkedIn public profile URL check
                if input_type == ScanInputType.USERNAME:
                    url = f"https://www.linkedin.com/in/{input_value}"
                    try:
                        resp = await client.get(url, headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        })
                        if resp.status_code == 200 and "linkedin.com" in str(resp.url):
                            profiles.append({
                                "url": str(resp.url),
                                "platform": "linkedin",
                                "username": input_value,
                            })
                            identifiers.append(f"url:{resp.url}")
                            identifiers.append("service:linkedin")
                    except Exception:
                        pass

                # Method 2: Google dork search for LinkedIn profiles
                search_query = f"site:linkedin.com/in/ \"{input_value}\""
                try:
                    resp = await client.get(
                        "https://www.google.com/search",
                        params={"q": search_query, "num": 5},
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                    )
                    if resp.status_code == 200:
                        # Extract LinkedIn URLs from Google results
                        import re
                        urls = re.findall(r'https://\w+\.linkedin\.com/in/[\w-]+', resp.text)
                        for u in set(urls[:5]):
                            if u not in [p.get("url") for p in profiles]:
                                profiles.append({"url": u, "platform": "linkedin"})
                                identifiers.append(f"url:{u}")
                        if urls:
                            identifiers.append("service:linkedin")
                except Exception:
                    pass

            return {
                "query": input_value,
                "platform": "linkedin",
                "profiles_found": len(profiles),
                "profiles": profiles,
                "found": len(profiles) > 0,
                "extracted_identifiers": identifiers,
            }

        except ImportError:
            return {"query": input_value, "profiles": [], "found": False, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("LinkedIn scan error", error=str(e))
            raise
