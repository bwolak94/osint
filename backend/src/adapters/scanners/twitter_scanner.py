"""Twitter/X scanner — checks for Twitter profile existence and public data."""

from typing import Any
import structlog
from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class TwitterScanner(BaseOsintScanner):
    """Checks if a username has a Twitter/X profile.

    Probes the public Twitter profile URL and extracts
    basic profile info from the page metadata.
    """

    scanner_name = "twitter"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            profile_data: dict[str, Any] = {
                "username": input_value,
                "platform": "twitter",
                "found": False,
                "url": f"https://x.com/{input_value}",
                "profile": {},
            }
            identifiers: list[str] = []

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                # Check X/Twitter profile
                try:
                    resp = await client.get(
                        f"https://x.com/{input_value}",
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                    )
                    if resp.status_code == 200 and "This account doesn" not in resp.text and input_value.lower() in resp.text.lower():
                        profile_data["found"] = True
                        identifiers.append(f"url:https://x.com/{input_value}")
                        identifiers.append("service:twitter")

                        # Try to extract description from meta tags
                        import re
                        desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', resp.text)
                        if desc_match:
                            profile_data["profile"]["description"] = desc_match.group(1)

                        title_match = re.search(r'<title>([^<]*)</title>', resp.text)
                        if title_match:
                            profile_data["profile"]["title"] = title_match.group(1)

                except Exception as e:
                    log.debug("Twitter check failed", error=str(e))

                # Also check via Nitter (open-source Twitter frontend) for better scraping
                try:
                    for nitter_instance in ["nitter.net", "nitter.privacydev.net"]:
                        resp = await client.get(
                            f"https://{nitter_instance}/{input_value}",
                            headers={"User-Agent": "Mozilla/5.0"},
                            timeout=10,
                        )
                        if resp.status_code == 200 and "not found" not in resp.text.lower():
                            profile_data["found"] = True
                            if not identifiers:
                                identifiers.append(f"url:https://x.com/{input_value}")
                                identifiers.append("service:twitter")
                            break
                except Exception:
                    pass

            profile_data["extracted_identifiers"] = identifiers
            return profile_data

        except ImportError:
            return {"username": input_value, "found": False, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("Twitter scan error", error=str(e))
            raise
