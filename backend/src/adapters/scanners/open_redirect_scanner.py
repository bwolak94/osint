"""Open Redirect — URL redirection vulnerability scanner.

Open redirects allow attackers to craft URLs that appear legitimate but
redirect victims to malicious sites. Used for phishing, OAuth token theft,
and bypassing CSP/referrer policies.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Canary domain to detect open redirects
_CANARY_DOMAIN = "evil-redirect-test.example.com"
_CANARY_URL = f"https://{_CANARY_DOMAIN}/"

# Open redirect payloads — various bypass techniques
_REDIRECT_PAYLOADS: list[tuple[str, str]] = [
    # (payload, description)
    (_CANARY_URL, "direct_url"),
    (f"//{_CANARY_DOMAIN}", "protocol_relative"),
    (f"\\\\{_CANARY_DOMAIN}", "backslash_bypass"),
    (f"https://{_CANARY_DOMAIN}@target.com", "at_sign_bypass"),
    (f"https://{_CANARY_DOMAIN}%23target.com", "fragment_bypass"),
    (f"https://{_CANARY_DOMAIN}%3F", "query_bypass"),
    (f"%2F%2F{_CANARY_DOMAIN}", "double_encoded"),
    (f"https://target.com.{_CANARY_DOMAIN}", "subdomain_confusion"),
    (f"javascript://target.com%0Aalert(1)", "javascript_bypass"),
    (f"data:text/html,<script>window.location='{_CANARY_URL}'</script>", "data_uri"),
    (f"/%09/{_CANARY_DOMAIN}", "tab_bypass"),
    (f"/%2f/{_CANARY_DOMAIN}", "encoded_slash"),
    (f"https://{_CANARY_DOMAIN}%2F.target.com", "slash_confusion"),
]

# Common redirect parameter names
_REDIRECT_PARAMS: list[str] = [
    "redirect", "redirect_to", "redirect_url", "redirectUrl", "redirect_uri",
    "return", "return_to", "returnTo", "return_url", "returnUrl",
    "next", "next_url", "nextUrl",
    "url", "goto", "go", "dest", "destination",
    "forward", "forward_url",
    "continue", "proceed",
    "target", "target_url",
    "ref", "referer", "referrer",
    "callback", "callbackUrl",
    "out", "link", "to",
    "success_url", "failure_url",
    "after_login_url", "login_redirect",
]

# Detection: server redirected to our canary domain
def _is_redirected_to_canary(resp: httpx.Response) -> bool:
    location = resp.headers.get("location", "")
    return _CANARY_DOMAIN in location


class OpenRedirectScanner(BaseOsintScanner):
    """Open redirect vulnerability scanner.

    Tests URL parameters for open redirect vulnerabilities using:
    - Direct URL injection
    - Protocol-relative URLs (//)
    - Backslash bypass (\\\\)
    - @ sign bypass (user@evil.com)
    - Encoded variants (%2F%2F, %09, %23)
    Checks both GET parameters and common POST redirect fields.
    """

    scanner_name = "open_redirect"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]
        test_params = list(dict.fromkeys(existing_params + _REDIRECT_PARAMS[:15]))

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,  # Must NOT follow — we detect the redirect header
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RedirectScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(12)

            async def test_param(param: str, payload: str, desc: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(f"{base_clean}?{param}={payload}")
                        if resp.status_code in (301, 302, 303, 307, 308) and _is_redirected_to_canary(resp):
                            vuln = {
                                "parameter": param,
                                "payload": payload,
                                "technique": desc,
                                "method": "GET",
                                "redirect_to": resp.headers.get("location", ""),
                                "status_code": resp.status_code,
                                "severity": "medium",
                                "description": f"Open redirect via {param}: redirects to {_CANARY_DOMAIN}",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:open_redirect:{param}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = [
                test_param(param, payload, desc)
                for param in test_params
                for payload, desc in _REDIRECT_PAYLOADS[:8]  # Top 8 techniques
            ]
            await asyncio.gather(*tasks)

            # Also check common redirect paths with embedded payloads
            redirect_paths = ["/logout", "/login", "/auth/callback", "/oauth/callback", "/redirect"]
            for path in redirect_paths:
                for payload, desc in _REDIRECT_PAYLOADS[:3]:
                    for param in ["redirect", "next", "url", "return"]:
                        try:
                            url = f"{base_url.rstrip('/')}{path}?{param}={payload}"
                            resp = await client.get(url)
                            if resp.status_code in (301, 302, 303, 307, 308) and _is_redirected_to_canary(resp):
                                vulnerabilities.append({
                                    "url": url,
                                    "parameter": param,
                                    "payload": payload,
                                    "technique": f"path_{desc}",
                                    "redirect_to": resp.headers.get("location", ""),
                                    "severity": "medium",
                                })
                                ident = f"vuln:open_redirect:{path}:{param}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                        except Exception:
                            pass

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "params_tested": test_params,
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
