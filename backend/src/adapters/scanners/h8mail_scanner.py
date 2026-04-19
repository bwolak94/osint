"""h8mail scanner — email breach hunter using free data sources."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_HIBP_BREACHES_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
_HIBP_PASTES_URL = "https://haveibeenpwned.com/api/v3/pasteaccount/{email}"
_HIBP_ALL_BREACHES_URL = "https://haveibeenpwned.com/api/v3/breaches"
_BREACH_DIRECTORY_URL = "https://breachdirectory.org/api/search?email={email}"

_HEADERS_BASE = {
    "User-Agent": "OSINT-Platform/1.0 (security research)",
    "Accept": "application/json",
}


class H8mailScanner(BaseOsintScanner):
    scanner_name = "h8mail"
    supported_input_types = frozenset({ScanInputType.EMAIL, ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()

        if input_type == ScanInputType.EMAIL:
            return await self._scan_email(input_value, settings.hibp_api_key)
        return await self._scan_domain(input_value, settings.hibp_api_key)

    async def _scan_email(self, email: str, hibp_key: str) -> dict[str, Any]:
        sources_checked: list[str] = []
        breaches: list[dict[str, Any]] = []
        paste_count = 0

        async with httpx.AsyncClient(timeout=15, headers=_HEADERS_BASE) as client:
            # 1. HIBP breaches
            if hibp_key:
                hibp_result = await self._check_hibp_breaches(client, email, hibp_key)
                sources_checked.append("HIBP")
                breaches.extend(hibp_result.get("breaches", []))

                paste_count = await self._check_hibp_pastes(client, email, hibp_key)
                sources_checked.append("HIBP_Pastes")
            else:
                log.debug("HIBP API key not configured; skipping HIBP checks")

            # 2. Attempt h8mail library
            h8mail_breaches = await self._try_h8mail_library(email)
            if h8mail_breaches:
                sources_checked.append("h8mail_library")
                # Merge, avoiding duplicates by breach name
                existing_names = {b.get("name", "") for b in breaches}
                for b in h8mail_breaches:
                    if b.get("name", "") not in existing_names:
                        breaches.append(b)

            # 3. BreachDirectory free tier
            bd_breaches = await self._check_breach_directory(client, email)
            if bd_breaches is not None:
                sources_checked.append("BreachDirectory")
                existing_names = {b.get("name", "") for b in breaches}
                for b in bd_breaches:
                    if b.get("name", "") not in existing_names:
                        breaches.append(b)

        return {
            "input": email,
            "input_type": "email",
            "breach_count": len(breaches),
            "breaches": breaches,
            "paste_count": paste_count,
            "sources_checked": sources_checked,
            "extracted_identifiers": [],
        }

    async def _scan_domain(self, domain: str, hibp_key: str) -> dict[str, Any]:
        sources_checked: list[str] = []
        breaches: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=15, headers=_HEADERS_BASE) as client:
            if hibp_key:
                try:
                    resp = await client.get(
                        _HIBP_ALL_BREACHES_URL,
                        headers={**_HEADERS_BASE, "hibp-api-key": hibp_key},
                    )
                    if resp.status_code == 200:
                        all_breaches: list[dict[str, Any]] = resp.json()
                        domain_lower = domain.lower()
                        breaches = [
                            {
                                "name": b.get("Name", ""),
                                "date": b.get("BreachDate", ""),
                                "data_classes": b.get("DataClasses", []),
                                "pwn_count": b.get("PwnCount", 0),
                                "domain": b.get("Domain", ""),
                            }
                            for b in all_breaches
                            if b.get("Domain", "").lower() == domain_lower
                        ]
                        sources_checked.append("HIBP_AllBreaches")
                    elif resp.status_code == 429:
                        raise RateLimitError("HIBP rate limit exceeded")
                except RateLimitError:
                    raise
                except Exception as exc:
                    log.debug("HIBP all-breaches lookup failed", domain=domain, error=str(exc))
            else:
                log.debug("HIBP API key not configured; skipping domain breach check")

        return {
            "input": domain,
            "input_type": "domain",
            "breach_count": len(breaches),
            "breaches": breaches,
            "paste_count": 0,
            "sources_checked": sources_checked,
            "extracted_identifiers": [],
        }

    async def _check_hibp_breaches(
        self,
        client: httpx.AsyncClient,
        email: str,
        api_key: str,
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _HIBP_BREACHES_URL.format(email=email),
                headers={**_HEADERS_BASE, "hibp-api-key": api_key},
                params={"truncateResponse": "false"},
            )
            if resp.status_code == 404:
                return {"breaches": []}
            if resp.status_code == 429:
                raise RateLimitError("HIBP rate limit exceeded")
            if resp.status_code != 200:
                return {"breaches": []}

            raw: list[dict[str, Any]] = resp.json()
            breaches = [
                {
                    "name": b.get("Name", ""),
                    "title": b.get("Title", ""),
                    "date": b.get("BreachDate", ""),
                    "pwn_count": b.get("PwnCount", 0),
                    "data_classes": b.get("DataClasses", []),
                    "description": b.get("Description", ""),
                    "domain": b.get("Domain", ""),
                    "is_verified": b.get("IsVerified", False),
                }
                for b in raw
            ]
            return {"breaches": breaches}
        except RateLimitError:
            raise
        except Exception as exc:
            log.debug("HIBP breach check failed", email=email, error=str(exc))
            return {"breaches": []}

    async def _check_hibp_pastes(
        self,
        client: httpx.AsyncClient,
        email: str,
        api_key: str,
    ) -> int:
        try:
            resp = await client.get(
                _HIBP_PASTES_URL.format(email=email),
                headers={**_HEADERS_BASE, "hibp-api-key": api_key},
            )
            if resp.status_code == 404:
                return 0
            if resp.status_code == 429:
                raise RateLimitError("HIBP rate limit exceeded")
            if resp.status_code != 200:
                return 0
            pastes: list[dict[str, Any]] = resp.json()
            return len(pastes)
        except RateLimitError:
            raise
        except Exception as exc:
            log.debug("HIBP paste check failed", email=email, error=str(exc))
            return 0

    async def _try_h8mail_library(self, email: str) -> list[dict[str, Any]]:
        """Attempt to use the h8mail library if installed."""
        try:
            from h8mail.utils.classes import target as H8Target  # type: ignore[import]
            import asyncio

            loop = asyncio.get_running_loop()
            t = await loop.run_in_executor(None, lambda: H8Target(email))
            raw_results: list[Any] = getattr(t, "data", [])
            return [
                {"name": str(r), "date": "", "data_classes": []}
                for r in raw_results
            ]
        except ImportError:
            return []
        except Exception as exc:
            log.debug("h8mail library call failed", email=email, error=str(exc))
            return []

    async def _check_breach_directory(
        self,
        client: httpx.AsyncClient,
        email: str,
    ) -> list[dict[str, Any]] | None:
        """Query BreachDirectory free API tier."""
        try:
            resp = await client.get(
                _BREACH_DIRECTORY_URL.format(email=email),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                return [
                    {
                        "name": r.get("sources", ["BreachDirectory"])[0]
                        if r.get("sources")
                        else "BreachDirectory",
                        "date": "",
                        "data_classes": r.get("fields", []),
                        "has_password": r.get("has_password", False),
                    }
                    for r in results
                ]
            return None
        except Exception as exc:
            log.debug("BreachDirectory check failed", email=email, error=str(exc))
            return None

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
