"""Have I Been Pwned (HIBP) breach scanner — checks email addresses against known data breaches."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class BreachScanner(BaseOsintScanner):
    """Queries the HIBP v3 API to find breaches associated with an email address.

    Requires a paid API key (hibp-key header). If no key is configured,
    returns a stub result with a note explaining that the key is required.
    """

    scanner_name = "hibp"
    supported_input_types = frozenset({ScanInputType.EMAIL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()
        api_key = settings.hibp_api_key

        if not api_key:
            return {
                "email": input_value,
                "found": False,
                "breaches": [],
                "note": "HIBP API key is not configured. Set HIBP_API_KEY in your environment to enable breach lookups.",
                "extracted_identifiers": [],
                "_stub": True,
            }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{input_value}",
                headers={
                    "hibp-api-key": api_key,
                    "User-Agent": "OSINT-Platform",
                },
                params={"truncateResponse": "false"},
            )

            # 404 means the email was not found in any breaches
            if resp.status_code == 404:
                return {
                    "email": input_value,
                    "found": False,
                    "breaches": [],
                    "total_breaches": 0,
                    "extracted_identifiers": [],
                }

            resp.raise_for_status()
            breaches = resp.json()

        breach_summaries: list[dict[str, Any]] = []
        identifiers: list[str] = []

        for breach in breaches:
            name = breach.get("Name", "")
            breach_summaries.append({
                "name": name,
                "title": breach.get("Title", ""),
                "domain": breach.get("Domain", ""),
                "breach_date": breach.get("BreachDate", ""),
                "added_date": breach.get("AddedDate", ""),
                "pwn_count": breach.get("PwnCount", 0),
                "data_classes": breach.get("DataClasses", []),
                "is_verified": breach.get("IsVerified", False),
                "is_sensitive": breach.get("IsSensitive", False),
            })
            if name:
                identifiers.append(f"breach:{name}")

        return {
            "email": input_value,
            "found": True,
            "total_breaches": len(breach_summaries),
            "breaches": breach_summaries,
            "extracted_identifiers": identifiers,
        }
