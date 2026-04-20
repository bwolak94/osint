"""Socialscan scanner — check username/email availability across social platforms."""

import asyncio
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_PLATFORM_STATUS_REGISTERED = "registered"
_PLATFORM_STATUS_AVAILABLE = "available"
_PLATFORM_STATUS_UNKNOWN = "unknown"


class SocialscanScanner(BaseOsintScanner):
    scanner_name = "socialscan"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 1800

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Attempt to use socialscan library first
        try:
            return await self._run_socialscan_library(input_value, input_type)
        except ImportError:
            log.debug("socialscan library not installed, using direct checks")
        except Exception as exc:
            log.debug("socialscan library failed, falling back to direct checks", error=str(exc))

        return await self._direct_checks(input_value, input_type)

    async def _run_socialscan_library(
        self,
        input_value: str,
        input_type: ScanInputType,
    ) -> dict[str, Any]:
        from socialscan.util import Platforms, sync_execute_queries  # type: ignore[import]

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: sync_execute_queries([input_value], [p for p in Platforms]),
        )
        platform_results: dict[str, str] = {}
        for res in results:
            if res.available is True:
                platform_results[res.platform] = _PLATFORM_STATUS_AVAILABLE
            elif res.available is False:
                platform_results[res.platform] = _PLATFORM_STATUS_REGISTERED
            else:
                platform_results[res.platform] = _PLATFORM_STATUS_UNKNOWN

        registered_count = sum(1 for v in platform_results.values() if v == _PLATFORM_STATUS_REGISTERED)
        available_count = sum(1 for v in platform_results.values() if v == _PLATFORM_STATUS_AVAILABLE)

        return {
            "input": input_value,
            "input_type": input_type.value,
            "source": "socialscan_library",
            "platform_results": platform_results,
            "registered_count": registered_count,
            "available_count": available_count,
            "extracted_identifiers": [],
        }

    async def _direct_checks(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        """Directly query key platforms to determine username/email availability."""
        platform_results: dict[str, str] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        ) as client:
            if input_type == ScanInputType.USERNAME:
                results = await asyncio.gather(
                    self._check_reddit_username(client, input_value),
                    self._check_github_username(client, input_value),
                    self._check_twitter_username(client, input_value),
                    self._check_instagram_username(client, input_value),
                    self._check_twitch_username(client, input_value),
                    return_exceptions=True,
                )
                platforms = ["Reddit", "GitHub", "Twitter", "Instagram", "Twitch"]
            else:
                results = await asyncio.gather(
                    self._check_email_mx(input_value),
                    return_exceptions=True,
                )
                platforms = ["MXRecord"]

        for platform, result in zip(platforms, results):
            if isinstance(result, Exception):
                platform_results[platform] = _PLATFORM_STATUS_UNKNOWN
            else:
                platform_results[platform] = result  # type: ignore[assignment]

        registered_count = sum(1 for v in platform_results.values() if v == _PLATFORM_STATUS_REGISTERED)
        available_count = sum(1 for v in platform_results.values() if v == _PLATFORM_STATUS_AVAILABLE)

        return {
            "input": input_value,
            "input_type": input_type.value,
            "source": "direct_checks",
            "platform_results": platform_results,
            "registered_count": registered_count,
            "available_count": available_count,
            "extracted_identifiers": [],
        }

    async def _check_reddit_username(self, client: httpx.AsyncClient, username: str) -> str:
        try:
            resp = await client.post(
                "https://www.reddit.com/api/check_username.json",
                json={"user": username},
                headers={"Content-Type": "application/json"},
            )
            data = resp.json()
            # Reddit returns {"error": "..."} when taken, empty object when available
            if "error" in data:
                return _PLATFORM_STATUS_REGISTERED
            return _PLATFORM_STATUS_AVAILABLE
        except Exception:
            return _PLATFORM_STATUS_UNKNOWN

    async def _check_github_username(self, client: httpx.AsyncClient, username: str) -> str:
        try:
            resp = await client.get(f"https://api.github.com/users/{username}")
            if resp.status_code == 404:
                return _PLATFORM_STATUS_AVAILABLE
            if resp.status_code == 200:
                return _PLATFORM_STATUS_REGISTERED
            return _PLATFORM_STATUS_UNKNOWN
        except Exception:
            return _PLATFORM_STATUS_UNKNOWN

    async def _check_twitter_username(self, client: httpx.AsyncClient, username: str) -> str:
        try:
            resp = await client.head(f"https://twitter.com/{username}")
            if resp.status_code == 404:
                return _PLATFORM_STATUS_AVAILABLE
            if resp.status_code == 200:
                return _PLATFORM_STATUS_REGISTERED
            return _PLATFORM_STATUS_UNKNOWN
        except Exception:
            return _PLATFORM_STATUS_UNKNOWN

    async def _check_instagram_username(self, client: httpx.AsyncClient, username: str) -> str:
        try:
            resp = await client.get(f"https://www.instagram.com/{username}/")
            if resp.status_code == 404 or "Page Not Found" in resp.text:
                return _PLATFORM_STATUS_AVAILABLE
            if resp.status_code == 200:
                return _PLATFORM_STATUS_REGISTERED
            return _PLATFORM_STATUS_UNKNOWN
        except Exception:
            return _PLATFORM_STATUS_UNKNOWN

    async def _check_twitch_username(self, client: httpx.AsyncClient, username: str) -> str:
        try:
            resp = await client.get(f"https://www.twitch.tv/{username}")
            if resp.status_code == 404:
                return _PLATFORM_STATUS_AVAILABLE
            if resp.status_code == 200:
                return _PLATFORM_STATUS_REGISTERED
            return _PLATFORM_STATUS_UNKNOWN
        except Exception:
            return _PLATFORM_STATUS_UNKNOWN

    async def _check_email_mx(self, email: str) -> str:
        """Check MX record existence for the email domain."""
        try:
            import dns.resolver  # type: ignore[import]

            domain = email.split("@", 1)[1]
            loop = asyncio.get_running_loop()
            records = await loop.run_in_executor(
                None, lambda: dns.resolver.resolve(domain, "MX")
            )
            if records:
                return _PLATFORM_STATUS_REGISTERED
            return _PLATFORM_STATUS_AVAILABLE
        except Exception:
            return _PLATFORM_STATUS_UNKNOWN

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
