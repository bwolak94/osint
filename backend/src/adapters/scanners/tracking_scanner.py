"""Tracking Code Scanner — extracts analytics/advertising IDs and pivots to co-hosted sites.

Infrastructure fingerprinting via shared tracking codes is one of the most
effective techniques for linking disparate websites to a single operator.
A single Google Analytics UA-XXXXXX-X ID routinely links 50-500 domains.

Tracking codes detected:
  - Google Analytics UA (Universal Analytics)
  - Google Analytics 4 (G-XXXXXXXXXX)
  - Google Tag Manager (GTM-XXXXXXX)
  - Google AdSense (pub-XXXXXXXXXXXXXXXX)
  - Yandex.Metrica
  - Facebook Pixel
  - Hotjar
  - Bing UET

Pivot sources (finding OTHER sites using the same code):
  1. SpyOnWeb API    — requires API key (spyonweb_api_key in settings)
  2. PublicWWW       — free fallback, rate-limited (20 results)

Input entities:  DOMAIN, URL
Output entities: TRACKING_CODE, DOMAIN (related sites sharing the same codes)
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Regex patterns for common tracking codes
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, re.Pattern[str]] = {
    "google_analytics_ua": re.compile(r"UA-(\d{4,12}-\d{1,4})", re.IGNORECASE),
    "google_analytics_4":  re.compile(r"\bG-([A-Z0-9]{6,14})\b", re.IGNORECASE),
    "google_tag_manager":  re.compile(r"\bGTM-([A-Z0-9]{5,8})\b", re.IGNORECASE),
    "google_adsense":      re.compile(r"pub-(\d{16})", re.IGNORECASE),
    "yandex_metrica":      re.compile(
        r"(?:metrika\.yandex\.|ym\()\s*['\"]?(\d{7,10})", re.IGNORECASE
    ),
    "facebook_pixel":      re.compile(
        r"fbq\s*\(\s*['\"]init['\"]\s*,\s*['\"](\d{14,17})['\"]", re.IGNORECASE
    ),
    "hotjar":              re.compile(r"hjid\s*[:=]\s*(\d{6,10})", re.IGNORECASE),
    "bing_uet":            re.compile(r"UET\(['\"]([A-Z0-9]{10,15})['\"]", re.IGNORECASE),
    "amazon_associates":   re.compile(r"tag=([a-z0-9-]{5,30}-20)", re.IGNORECASE),
    "tiktok_pixel":        re.compile(r"ttq\.load\s*\(\s*['\"]([A-Z0-9]{18,20})['\"]", re.IGNORECASE),
}

# Which code types SpyOnWeb supports
_SPYONWEB_ENDPOINTS: dict[str, str] = {
    "google_analytics_ua": "https://api.spyonweb.com/v1/analytics/{code}",
    "google_adsense":      "https://api.spyonweb.com/v1/adsense/{code}",
}

_PUBLICWWW_PIVOTABLE = {"google_analytics_ua", "google_analytics_4", "google_adsense"}

_REQUEST_TIMEOUT = 20.0
_MAX_RELATED_PER_CODE = 50


class TrackingCodeScanner(BaseOsintScanner):
    """Fetch a website's HTML, extract tracking codes, pivot to co-hosted domains.

    Input:  ScanInputType.DOMAIN or ScanInputType.URL
    Output: tracking_code: and domain: identifiers

    The pivot (finding other sites sharing the same GA/AdSense ID) is the
    core intelligence value — it clusters domains under a single operator.
    """

    scanner_name = "tracking_codes"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target_url = (
            input_value if input_value.startswith("http") else f"https://{input_value}"
        )
        domain = urlparse(target_url).netloc or input_value

        codes: dict[str, list[str]] = {}
        related_domains: dict[str, list[str]] = {}

        settings = get_settings()
        spyonweb_key: str = getattr(settings, "spyonweb_api_key", "")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_REQUEST_TIMEOUT),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; OSINTResearch/1.0)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            # Step 1 — fetch target page HTML
            html = await self._fetch_page(client, target_url)
            if html:
                codes = self._extract_all_codes(html)
                log.info(
                    "Tracking codes found",
                    domain=domain,
                    types=list(codes.keys()),
                    total=sum(len(v) for v in codes.values()),
                )

            # Step 2 — pivot each code to find related domains
            for code_type, code_list in codes.items():
                for code in code_list:
                    pivot_result = await self._pivot(
                        client, code, code_type, spyonweb_key, domain
                    )
                    if pivot_result:
                        related_domains[f"{code_type}:{code}"] = pivot_result

        # Build flat identifiers list
        all_codes_flat = [
            f"{ctype}:{c}" for ctype, clist in codes.items() for c in clist
        ]
        identifiers: list[str] = [f"tracking:{c}" for c in all_codes_flat]
        related_flat: set[str] = set()
        for domains in related_domains.values():
            related_flat.update(domains)
        identifiers += [f"domain:{d}" for d in sorted(related_flat)]

        return {
            "domain": domain,
            "url": target_url,
            "found": bool(codes),
            "tracking_codes": codes,
            "tracking_codes_flat": all_codes_flat,
            "related_domains": related_domains,
            "related_domain_count": len(related_flat),
            "pivot_source": "spyonweb" if spyonweb_key else "publicwww_fallback",
            "extracted_identifiers": identifiers,
        }

    # ------------------------------------------------------------------
    # HTML fetch
    # ------------------------------------------------------------------

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as exc:
            log.warning("Page fetch HTTP error", url=url, status=exc.response.status_code)
            return ""
        except Exception as exc:
            log.warning("Page fetch failed", url=url, error=str(exc))
            return ""

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_all_codes(self, html: str) -> dict[str, list[str]]:
        """Apply all regex patterns to HTML source, return de-duplicated matches."""
        results: dict[str, list[str]] = {}
        for name, pattern in _PATTERNS.items():
            matches = list(dict.fromkeys(pattern.findall(html)))
            if matches:
                results[name] = matches
        return results

    # ------------------------------------------------------------------
    # Pivoting
    # ------------------------------------------------------------------

    async def _pivot(
        self,
        client: httpx.AsyncClient,
        code: str,
        code_type: str,
        spyonweb_key: str,
        exclude_domain: str,
    ) -> list[str]:
        """Find other domains using the same tracking code."""
        if spyonweb_key and code_type in _SPYONWEB_ENDPOINTS:
            result = await self._pivot_spyonweb(client, code, code_type, spyonweb_key)
        elif code_type in _PUBLICWWW_PIVOTABLE:
            result = await self._pivot_publicwww(client, code)
        else:
            return []

        return [d for d in result if d and d != exclude_domain][:_MAX_RELATED_PER_CODE]

    async def _pivot_spyonweb(
        self,
        client: httpx.AsyncClient,
        code: str,
        code_type: str,
        api_key: str,
    ) -> list[str]:
        """Query SpyOnWeb API to find domains sharing the tracking code."""
        endpoint = _SPYONWEB_ENDPOINTS[code_type].format(code=code)
        try:
            resp = await client.get(endpoint, params={"access_token": api_key})
            if resp.status_code == 404:
                return []
            if resp.status_code == 429:
                log.warning("SpyOnWeb rate limited", code=code)
                return []
            resp.raise_for_status()
            data = resp.json()

            domains: list[str] = []
            for _code_key, code_data in data.get("result", {}).items():
                domains.extend(code_data.get("items", {}).keys())
            return domains
        except Exception as exc:
            log.warning("SpyOnWeb pivot error", code=code, error=str(exc))
            return []

    async def _pivot_publicwww(self, client: httpx.AsyncClient, code: str) -> list[str]:
        """Fallback pivot via PublicWWW source code search (free, limited results)."""
        try:
            resp = await client.get(
                f"https://publicwww.com/websites/{code}/",
                headers={"Accept": "text/html"},
            )
            if resp.status_code != 200:
                return []

            # Extract domain links from PublicWWW results page
            domain_re = re.compile(
                r'href="https?://publicwww\.com/websites/[^/]+/"\s*[^>]*>([a-z0-9.\-]+\.[a-z]{2,})<',
                re.IGNORECASE,
            )
            found = domain_re.findall(resp.text)

            # Broader fallback — any link to external domain
            if not found:
                broad_re = re.compile(r'href="https?://([a-z0-9.\-]+\.[a-z]{2,})/', re.IGNORECASE)
                all_links = broad_re.findall(resp.text)
                found = [d for d in all_links if "publicwww" not in d]

            return list(dict.fromkeys(found))[:20]
        except Exception as exc:
            log.warning("PublicWWW pivot error", code=code, error=str(exc))
            return []

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
