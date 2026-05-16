"""Web Cache Poisoning — unkeyed header injection scanner.

Web cache poisoning exploits discrepancies between what the cache
stores and what the backend processes. Attackers inject malicious
content via unkeyed headers that gets cached and served to victims.

Techniques: X-Forwarded-Host, X-Forwarded-Scheme, X-Original-URL,
            X-Rewrite-URL, fat GET, header injection via newlines.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Cache indicator headers
_CACHE_HEADERS = [
    "X-Cache", "X-Cache-Status", "CF-Cache-Status", "Age",
    "X-Varnish", "Via", "X-Drupal-Cache", "X-WP-Cache",
    "X-Proxy-Cache", "Surrogate-Control", "CDN-Cache-Control",
    "Fastly-Cache-Status", "X-Cache-Lookup", "X-Served-By",
]

# Headers commonly unkeyed by caches
_UNKEYED_HEADERS: list[tuple[str, str, str]] = [
    # (header_name, injection_value, technique)
    ("X-Forwarded-Host", "CANARY_DOMAIN", "x_forwarded_host"),
    ("X-Forwarded-Port", "1337", "x_forwarded_port"),
    ("X-Forwarded-Scheme", "http", "scheme_downgrade"),
    ("X-Original-URL", "/CANARY_PATH", "x_original_url"),
    ("X-Rewrite-URL", "/CANARY_PATH", "x_rewrite_url"),
    ("X-Host", "CANARY_DOMAIN", "x_host"),
    ("X-Custom-IP-Authorization", "127.0.0.1", "ip_override"),
    ("X-Originating-IP", "127.0.0.1", "originating_ip"),
    ("X-Remote-IP", "127.0.0.1", "remote_ip_override"),
    ("X-Client-IP", "127.0.0.1", "client_ip_override"),
    ("X-HTTP-Method-Override", "DELETE", "method_override"),
    ("X-HTTP-Method", "PUT", "http_method"),
    ("X-Method-Override", "PATCH", "method_override_alt"),
]


class WebCachePoisoningScanner(BaseOsintScanner):
    """Web cache poisoning vulnerability scanner.

    Detects caching infrastructure and tests for unkeyed header injection.
    Identifies headers that are processed by the backend but not included
    in the cache key, enabling cache poisoning attacks.
    """

    scanner_name = "web_cache_poisoning"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        cache_found: dict[str, str] = {}
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        canary_id = uuid.uuid4().hex[:8]
        canary_domain = f"cache-poison-{canary_id}.evil.com"
        canary_path = f"/cache-poison-{canary_id}"

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CachePoisonScanner/1.0)"},
        ) as client:

            # Step 1: Detect caching layer
            try:
                resp1 = await client.get(base_url)
                resp2 = await client.get(base_url)

                for ch in _CACHE_HEADERS:
                    val = resp1.headers.get(ch, "")
                    if val:
                        cache_found[ch] = val

                # Age header increasing = cached
                age1 = int(resp1.headers.get("Age", "0") or "0")
                age2 = int(resp2.headers.get("Age", "0") or "0")
                if age2 > age1:
                    cache_found["age_increment"] = f"{age1} → {age2}"

                is_cached = bool(cache_found)

            except Exception as exc:
                log.debug("Cache detection failed", url=base_url, error=str(exc))
                is_cached = False

            if not is_cached:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "cache_detected": False,
                    "cache_headers": cache_found,
                    "vulnerabilities": [],
                    "note": "No caching layer detected — cache poisoning unlikely",
                    "extracted_identifiers": [],
                }

            semaphore = asyncio.Semaphore(6)

            async def test_unkeyed_header(header: str, value: str, technique: str) -> None:
                async with semaphore:
                    actual_value = value.replace("CANARY_DOMAIN", canary_domain).replace("CANARY_PATH", canary_path)
                    try:
                        # Send request with injected header
                        resp = await client.get(
                            base_url,
                            headers={
                                "User-Agent": "Mozilla/5.0",
                                header: actual_value,
                            },
                        )
                        body = resp.text

                        # Check if canary value appears in response
                        if canary_domain in body or canary_path in body:
                            vuln = {
                                "header": header,
                                "injected_value": actual_value,
                                "technique": technique,
                                "severity": "high",
                                "description": f"Header '{header}' value reflected in response — potential unkeyed header",
                                "evidence": "Canary value found in response body",
                            }
                            vulnerabilities.append(vuln)
                            identifiers.append(f"vuln:cache_poison:{technique}")

                        # Check if response differs (cache miss vs hit indicators)
                        cache_miss = resp.headers.get("X-Cache", "").lower() in ("miss", "bypass")
                        if cache_miss and header in ("X-Forwarded-Host", "X-Host"):
                            # Different cache behavior with our header = likely unkeyed
                            vuln = {
                                "header": header,
                                "injected_value": actual_value[:50],
                                "technique": technique,
                                "severity": "medium",
                                "description": f"Cache miss with modified '{header}' — header may affect response without being in cache key",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:cache_poison:miss:{header}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Method override attack — if server processes it
                        if technique == "method_override" and resp.status_code in (200, 405):
                            vuln = {
                                "header": header,
                                "injected_value": actual_value,
                                "technique": technique,
                                "severity": "medium",
                                "description": f"HTTP method override via '{header}' may be processed",
                            }
                            vulnerabilities.append(vuln)

                    except Exception:
                        pass

            tasks = [test_unkeyed_header(h, v, t) for h, v, t in _UNKEYED_HEADERS]
            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "cache_detected": is_cached,
            "cache_headers": cache_found,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "canary_id": canary_id,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
