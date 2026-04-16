"""Facebook scanner — checks for Facebook profile existence."""

from typing import Any
import structlog
from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class FacebookScanner(BaseOsintScanner):
    """Checks if a username has a Facebook profile.

    Probes the public Facebook profile URL. Note that Facebook
    heavily restricts scraping, so results may be limited.
    """

    scanner_name = "facebook"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            identifiers: list[str] = []
            found = False

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                try:
                    resp = await client.get(
                        f"https://www.facebook.com/{input_value}",
                        headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                            "Accept-Language": "en-US,en;q=0.9",
                        },
                    )
                    # Facebook returns 200 for existing profiles, redirects for non-existent
                    if resp.status_code == 200 and "page not found" not in resp.text.lower() and "/login" not in str(resp.url):
                        found = True
                        identifiers.append(f"url:https://www.facebook.com/{input_value}")
                        identifiers.append("service:facebook")
                except Exception as e:
                    log.debug("Facebook check failed", error=str(e))

            return {
                "username": input_value,
                "platform": "facebook",
                "found": found,
                "url": f"https://www.facebook.com/{input_value}" if found else None,
                "extracted_identifiers": identifiers,
            }

        except ImportError:
            return {"username": input_value, "found": False, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("Facebook scan error", error=str(e))
            raise
