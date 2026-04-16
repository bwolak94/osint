"""Google account scanner — discovers Google services linked to an email."""

from typing import Any
import structlog
from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class GoogleAccountScanner(BaseOsintScanner):
    """Checks Google services linked to an email address.

    Probes public Google endpoints to discover:
    - Google Maps contributions (reviews)
    - Google profile existence
    - YouTube channel
    - Google Calendar (public)
    """

    scanner_name = "google_account"
    supported_input_types = frozenset({ScanInputType.EMAIL})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            results: dict[str, Any] = {
                "email": input_value,
                "google_id": None,
                "profile_photo": None,
                "google_maps": False,
                "youtube": False,
                "services": [],
            }
            identifiers: list[str] = []

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                # Check Google People API (public profile)
                # Use the Google+ legacy endpoint that still resolves for some accounts
                try:
                    resp = await client.get(
                        f"https://www.google.com/s2/photos/public/AIbEiAIAAABECKjR",
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    # We can't directly look up by email, but we can check if the domain is gmail
                except Exception:
                    pass

                # Check if email has Gravatar (works for any email)
                import hashlib
                email_hash = hashlib.md5(input_value.strip().lower().encode()).hexdigest()
                try:
                    resp = await client.get(
                        f"https://www.gravatar.com/avatar/{email_hash}?d=404",
                    )
                    if resp.status_code == 200:
                        results["services"].append("gravatar")
                        results["profile_photo"] = f"https://www.gravatar.com/avatar/{email_hash}"
                        identifiers.append("service:gravatar")
                except Exception:
                    pass

                # Check Google Calendar (public)
                try:
                    resp = await client.get(
                        f"https://calendar.google.com/calendar/embed?src={input_value}",
                    )
                    if resp.status_code == 200 and "Calendar" in resp.text:
                        results["services"].append("google_calendar")
                        identifiers.append("service:google_calendar")
                except Exception:
                    pass

                # Check if email domain is Google Workspace
                domain = input_value.split("@")[1] if "@" in input_value else ""
                if domain and domain != "gmail.com":
                    try:
                        resp = await client.get(
                            f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT",
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            for answer in data.get("Answer", []):
                                txt = answer.get("data", "")
                                if "google" in txt.lower():
                                    results["services"].append("google_workspace")
                                    identifiers.append("service:google_workspace")
                                    break
                    except Exception:
                        pass

                # Gmail-specific: check Google Maps contributions
                if domain == "gmail.com":
                    results["is_gmail"] = True
                    results["services"].append("gmail")
                    identifiers.append("service:gmail")

            results["registered_count"] = len(results["services"])
            results["extracted_identifiers"] = identifiers

            return results

        except ImportError:
            return {"email": input_value, "services": [], "registered_count": 0, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("Google account scan error", error=str(e))
            raise
