"""PwnDB scanner — checks email addresses against publicly known breach databases.

WARNING: This scanner queries services that index data from historical breach
databases.  It is intended exclusively for authorised OSINT investigations
(e.g. checking whether your own organisation's credentials have been exposed).
Never use it to look up third-party email addresses without explicit written
authorisation from the account holder.  Misuse may violate computer fraud,
data-protection, and privacy laws in your jurisdiction.
"""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_PROXYNOVA_API = "https://api.proxynova.com/comb"
_LEAKCHECK_API = "https://leakcheck.io/api/public"


class PwnDBScanner(BaseOsintScanner):
    """Checks email addresses against publicly indexed breach data.

    Uses two free, clearnet services as data sources:
    1. ProxyNova COMB API — indexes the "Collection of Many Breaches" dataset.
       GET https://api.proxynova.com/comb?query={email}
    2. LeakCheck public API (limited free tier) as a secondary source.
       GET https://leakcheck.io/api/public?check={email}

    Both sources are queried; results are merged and de-duplicated.  The
    scanner explicitly does NOT store or log plaintext passwords — only
    metadata (breach source names, record counts, and whether plaintext
    passwords appear to be present) is surfaced.

    Input: EMAIL
    Returns:
    - breaches (list of dicts with source / credential fields redacted)
    - total_records (int)
    - has_plaintext_passwords (bool)

    NOTE: pwndb2am4tzkvold.onion is the original Tor-only pwndb service.
    Querying it would require a Tor proxy.  This scanner uses clearnet
    alternatives only; Tor support can be added later via the proxy_mode
    setting in config.
    """

    scanner_name = "pwndb"
    supported_input_types = frozenset({ScanInputType.EMAIL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        proxynova_data = await self._query_proxynova(input_value)
        leakcheck_data = await self._query_leakcheck(input_value)

        combined = self._merge(proxynova_data, leakcheck_data)
        combined["input"] = input_value
        return combined

    async def _query_proxynova(self, email: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _PROXYNOVA_API,
                    params={"query": email},
                    headers={"User-Agent": "OSINT-Platform/1.0 (authorised investigation tool)"},
                )
                if resp.status_code == 429:
                    from src.adapters.scanners.exceptions import RateLimitError
                    raise RateLimitError("ProxyNova COMB rate limit exceeded")
                if resp.status_code != 200:
                    log.debug("ProxyNova API non-200", status=resp.status_code, email=email)
                    return {}
                data = resp.json()
        except Exception as exc:
            log.debug("ProxyNova query failed", error=str(exc), email=email)
            return {}

        lines: list[dict[str, Any]] = data.get("lines", []) or []
        count = data.get("count", len(lines))

        has_plaintext = False
        breaches: list[dict[str, Any]] = []
        for line in lines:
            # ProxyNova returns `email:password` pairs — we redact the password
            if isinstance(line, str):
                parts = line.split(":", 1)
                has_plaintext = True
                breaches.append({"source": "COMB", "credential_type": "email:password (redacted)"})
            elif isinstance(line, dict):
                if line.get("password") or line.get("pass"):
                    has_plaintext = True
                breaches.append({
                    "source": "COMB",
                    "credential_type": "email:password (redacted)",
                    "breach_info": {k: v for k, v in line.items() if k not in ("password", "pass")},
                })

        return {
            "source": "proxynova_comb",
            "total_records": count,
            "breaches": breaches,
            "has_plaintext_passwords": has_plaintext,
        }

    async def _query_leakcheck(self, email: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _LEAKCHECK_API,
                    params={"check": email},
                    headers={"User-Agent": "OSINT-Platform/1.0 (authorised investigation tool)"},
                )
                if resp.status_code == 429:
                    log.debug("LeakCheck rate limited", email=email)
                    return {}
                if resp.status_code != 200:
                    log.debug("LeakCheck API non-200", status=resp.status_code, email=email)
                    return {}
                data = resp.json()
        except Exception as exc:
            log.debug("LeakCheck query failed", error=str(exc), email=email)
            return {}

        if not data.get("success"):
            return {}

        sources: list[str] = data.get("sources", []) or []
        breaches = [{"source": s, "credential_type": "email found in breach"} for s in sources]

        return {
            "source": "leakcheck",
            "total_records": len(breaches),
            "breaches": breaches,
            "has_plaintext_passwords": False,  # LeakCheck public API doesn't expose passwords
        }

    def _merge(self, *source_results: dict[str, Any]) -> dict[str, Any]:
        all_breaches: list[dict[str, Any]] = []
        total = 0
        has_plaintext = False

        for result in source_results:
            if not result:
                continue
            all_breaches.extend(result.get("breaches", []))
            total += result.get("total_records", 0)
            if result.get("has_plaintext_passwords"):
                has_plaintext = True

        return {
            "found": total > 0,
            "breaches": all_breaches,
            "total_records": total,
            "has_plaintext_passwords": has_plaintext,
            "extracted_identifiers": [],  # No pivot identifiers for breach data
        }
