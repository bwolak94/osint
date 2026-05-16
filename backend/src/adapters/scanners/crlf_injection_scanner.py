"""CRLF Injection — HTTP response splitting vulnerability scanner.

CRLF (Carriage Return Line Feed) injection allows attackers to inject arbitrary
HTTP headers and body content by embedding \\r\\n sequences in user-controlled
input that gets reflected in Location, Set-Cookie, or other response headers.

Can lead to: response splitting, header injection, XSS via injected headers,
cache poisoning, and session fixation.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# CRLF injection payloads
_CRLF_PAYLOADS: list[tuple[str, str]] = [
    ("%0d%0aX-Injected-Header: injected", "url_encoded_crlf"),
    ("%0aX-Injected-Header: injected", "lf_only"),
    ("%0d%0a%0d%0a<html>injected</html>", "response_splitting"),
    ("\r\nX-Injected-Header: injected", "raw_crlf"),
    ("%0D%0AX-Injected-Header: injected", "uppercase_encoded"),
    ("%E5%98%8A%E5%98%8DX-Injected: crlf", "unicode_crlf"),   # UTF-8 CRLF
    ("%0d%0aSet-Cookie: crlf_session=injected", "cookie_injection"),
    ("%0d%0aLocation: https://evil.com", "location_injection"),
    ("\\r\\nX-Injected-Header: injected", "escaped_crlf"),
    ("%0d%0aContent-Type: text/html%0d%0a%0d%0a<script>alert(1)</script>", "xss_via_crlf"),
]

# Parameters that commonly appear in redirects / response headers
_INJECTABLE_PARAMS: list[str] = [
    "url", "redirect", "return", "next", "returnUrl", "returnTo",
    "goto", "target", "dest", "destination", "continue",
    "callback", "ref", "referer", "back",
]

# Paths that often reflect parameters in Location/Set-Cookie headers
_REFLECTIVE_PATHS: list[str] = [
    "/", "/login", "/logout", "/redirect", "/auth/login",
    "/api/login", "/api/redirect", "/goto", "/out",
    "/callback", "/sso", "/auth/callback",
]

# Marker to detect in response headers
_INJECTION_MARKER = "X-Injected-Header"
_COOKIE_MARKER = "crlf_session"


class CRLFInjectionScanner(BaseOsintScanner):
    """CRLF injection / HTTP response splitting vulnerability scanner.

    Injects CRLF sequences via URL parameters, query strings, and redirect
    parameters that commonly get reflected in HTTP response headers.
    """

    scanner_name = "crlf_injection"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CRLFScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            async def test_crlf(
                path: str, param: str, payload: str, technique: str
            ) -> None:
                async with semaphore:
                    # Inject in query parameter
                    url = f"{base_url.rstrip('/')}{path}?{param}={payload}"
                    try:
                        resp = await client.get(url)
                        all_headers = dict(resp.headers)
                        headers_str = str(all_headers).lower()
                        body = resp.text

                        # Check if injected header appears in response headers
                        if _INJECTION_MARKER.lower() in headers_str:
                            vulnerabilities.append({
                                "type": "crlf_header_injection",
                                "severity": "high",
                                "url": url,
                                "parameter": param,
                                "technique": technique,
                                "injected_header": _INJECTION_MARKER,
                                "description": f"CRLF injection via '{param}' parameter — arbitrary header injected",
                                "remediation": "Strip or encode CR (\\r) and LF (\\n) from all user input used in HTTP headers",
                            })
                            ident = f"vuln:crlf:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Check if injected cookie appears
                        set_cookie = resp.headers.get("set-cookie", "")
                        if _COOKIE_MARKER in set_cookie:
                            vulnerabilities.append({
                                "type": "crlf_cookie_injection",
                                "severity": "high",
                                "url": url,
                                "parameter": param,
                                "technique": technique,
                                "description": "CRLF injection allows arbitrary cookie injection — session fixation risk",
                                "remediation": "Sanitize user input; use strict output encoding in header values",
                            })
                            ident = f"vuln:crlf:cookie:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Check response splitting — injected HTML in body
                        if "<html>injected</html>" in body:
                            vulnerabilities.append({
                                "type": "crlf_response_splitting",
                                "severity": "critical",
                                "url": url,
                                "parameter": param,
                                "technique": technique,
                                "description": "HTTP response splitting via CRLF — attacker can inject full HTTP response",
                                "remediation": "Reject or strip all CRLF in user-controlled data; use whitelist validation",
                            })
                            ident = "vuln:crlf:response_splitting"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Check redirect to evil.com
                        location = resp.headers.get("location", "")
                        if "evil.com" in location and resp.status_code in (301, 302):
                            vulnerabilities.append({
                                "type": "crlf_location_injection",
                                "severity": "high",
                                "url": url,
                                "parameter": param,
                                "technique": technique,
                                "redirect_location": location[:80],
                                "description": "CRLF injection overwrites Location header — open redirect via header injection",
                            })
                            ident = "vuln:crlf:location"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            tasks = []
            for path in _REFLECTIVE_PATHS[:6]:
                for param in _INJECTABLE_PARAMS[:5]:
                    for payload, technique in _CRLF_PAYLOADS[:6]:
                        tasks.append(test_crlf(path, param, payload, technique))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
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
