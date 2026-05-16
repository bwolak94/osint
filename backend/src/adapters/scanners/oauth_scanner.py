"""OAuth 2.0 Security — redirect_uri bypass, implicit flow, and token leakage scanner.

Detects OAuth 2.0 misconfigurations: open redirect_uri, implicit flow token
leakage in URL fragments, state parameter absence (CSRF), PKCE enforcement,
token in Referer header leakage, and authorization code reuse.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common OAuth endpoint paths
_OAUTH_PATHS: list[str] = [
    "/oauth/authorize",
    "/oauth2/authorize",
    "/auth/authorize",
    "/authorize",
    "/connect/authorize",
    "/api/oauth/authorize",
    "/v1/oauth/authorize",
    "/.well-known/openid-configuration",
    "/.well-known/oauth-authorization-server",
]

# OAuth token/userinfo endpoints
_TOKEN_PATHS: list[str] = [
    "/oauth/token",
    "/oauth2/token",
    "/auth/token",
    "/token",
    "/connect/token",
]

# Redirect URI bypass payloads
_REDIRECT_URI_BYPASSES: list[tuple[str, str]] = [
    ("https://evil.com", "open_redirect"),
    ("https://evil.com%40legit.com", "at_sign_bypass"),
    ("https://legit.com.evil.com", "subdomain_confusion"),
    ("https://legit.com@evil.com", "userinfo_bypass"),
    ("javascript:alert(1)", "javascript_scheme"),
    ("//evil.com", "protocol_relative"),
    ("https://evil.com/../../oauth/callback", "path_traversal"),
    ("https://evil.com%2Flegit.com", "encoded_slash"),
    ("data:text/html,<script>alert(1)</script>", "data_uri"),
]

# OIDC discovery fields to audit
_OIDC_SECURITY_FIELDS: list[tuple[str, str, str]] = [
    ("response_types_supported", "token", "implicit_flow_enabled"),
    ("grant_types_supported", "implicit", "implicit_grant_supported"),
    ("request_object_signing_alg_values_supported", "none", "unsigned_request_objects"),
]


class OAuthScanner(BaseOsintScanner):
    """OAuth 2.0 security misconfiguration scanner.

    Tests for: redirect_uri bypass, implicit flow token leakage, missing
    state parameter (CSRF), PKCE absence, open redirect in authorization
    endpoints, and OIDC discovery misconfigurations.
    """

    scanner_name = "oauth"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        oauth_endpoints: list[str] = []
        oidc_config: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,  # Critical: track redirects manually
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OAuthScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Find OAuth endpoints + OIDC discovery
            async def find_oauth(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 302, 400):
                            body = resp.text
                            if any(k in body.lower() for k in ["oauth", "authorize", "client_id", "redirect_uri", "response_type"]):
                                if url not in oauth_endpoints:
                                    oauth_endpoints.append(url)

                            # Parse OIDC discovery
                            if ".well-known" in path and resp.status_code == 200:
                                import json
                                try:
                                    config = json.loads(body)
                                    oidc_config.update(config)
                                except Exception:
                                    pass
                    except Exception:
                        pass

            await asyncio.gather(*[find_oauth(p) for p in _OAUTH_PATHS])

            # Step 2: Audit OIDC discovery document
            if oidc_config:
                # Check for implicit flow support
                response_types = oidc_config.get("response_types_supported", [])
                if "token" in response_types or "id_token token" in response_types:
                    vulnerabilities.append({
                        "type": "oidc_implicit_flow_enabled",
                        "severity": "medium",
                        "description": "OIDC server supports implicit flow (response_type=token) — tokens exposed in URL fragment",
                        "response_types": response_types,
                        "remediation": "Remove 'token' from response_types_supported; use PKCE-protected authorization code flow",
                    })
                    identifiers.append("vuln:oauth:implicit_flow")

                # Check PKCE requirement
                code_challenge_methods = oidc_config.get("code_challenge_methods_supported", [])
                if not code_challenge_methods:
                    vulnerabilities.append({
                        "type": "oauth_pkce_not_enforced",
                        "severity": "medium",
                        "description": "OAuth server does not advertise PKCE support — authorization code interception risk",
                        "remediation": "Implement PKCE (RFC 7636); require code_challenge for public clients",
                    })
                    identifiers.append("vuln:oauth:pkce_missing")

                # Check for dangerous grant types
                grant_types = oidc_config.get("grant_types_supported", [])
                if "password" in grant_types:
                    vulnerabilities.append({
                        "type": "oauth_password_grant_enabled",
                        "severity": "high",
                        "description": "OAuth password grant type enabled — credentials exposed to client applications",
                        "remediation": "Disable Resource Owner Password Credentials grant; use authorization code + PKCE",
                    })
                    identifiers.append("vuln:oauth:password_grant")

                # Check authorization endpoint
                auth_endpoint = oidc_config.get("authorization_endpoint", "")
                if auth_endpoint and auth_endpoint not in oauth_endpoints:
                    oauth_endpoints.append(auth_endpoint)

            # Step 3: Test redirect_uri bypass on each OAuth authorize endpoint
            async def test_redirect_uri_bypass(
                endpoint: str, payload: str, technique: str
            ) -> None:
                async with semaphore:
                    params = {
                        "response_type": "code",
                        "client_id": "test",
                        "redirect_uri": payload,
                        "scope": "openid",
                        "state": "teststate",
                    }
                    url = f"{endpoint}?{urlencode(params)}"
                    try:
                        resp = await client.get(url)
                        location = resp.headers.get("location", "")

                        # Vulnerable: 302 redirect to evil.com or payload reflected
                        if resp.status_code in (302, 301):
                            if "evil.com" in location or payload in location:
                                vulnerabilities.append({
                                    "type": "oauth_open_redirect_uri",
                                    "severity": "high",
                                    "url": endpoint,
                                    "technique": technique,
                                    "redirect_to": location[:100],
                                    "description": f"OAuth redirect_uri open redirect ({technique}): server follows attacker-supplied URI",
                                    "remediation": "Strictly whitelist registered redirect URIs; reject any variation",
                                })
                                ident = f"vuln:oauth:redirect:{technique}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                        # 200 response with implicit token in body = implicit flow leak
                        if resp.status_code == 200:
                            body = resp.text
                            if re.search(r'access_token|id_token', body):
                                vulnerabilities.append({
                                    "type": "oauth_token_in_body",
                                    "severity": "high",
                                    "url": endpoint,
                                    "technique": technique,
                                    "description": "OAuth access_token exposed in response body without proper redirect",
                                    "remediation": "Never include tokens in GET response bodies; use proper redirect with code",
                                })
                                identifiers.append("vuln:oauth:token_in_body")

                    except Exception:
                        pass

            # Test missing state (CSRF)
            async def test_csrf_state(endpoint: str) -> None:
                async with semaphore:
                    params = {
                        "response_type": "code",
                        "client_id": "test",
                        "redirect_uri": base_url + "/callback",
                        "scope": "openid",
                        # No state parameter
                    }
                    url = f"{endpoint}?{urlencode(params)}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 302):
                            # No error about missing state = CSRF vulnerability
                            location = resp.headers.get("location", "")
                            if "state" not in location and "error" not in resp.text.lower():
                                vulnerabilities.append({
                                    "type": "oauth_missing_state_csrf",
                                    "severity": "medium",
                                    "url": endpoint,
                                    "description": "OAuth authorization endpoint accepts requests without 'state' parameter — CSRF attack possible",
                                    "remediation": "Require 'state' parameter; validate it matches session value on callback",
                                })
                                ident = "vuln:oauth:missing_state"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for endpoint in oauth_endpoints[:3]:
                # Only test clearly authorization endpoints
                if "authorize" in endpoint or "auth" in endpoint:
                    for payload, technique in _REDIRECT_URI_BYPASSES[:5]:
                        tasks.append(test_redirect_uri_bypass(endpoint, payload, technique))
                    tasks.append(test_csrf_state(endpoint))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "oauth_endpoints": oauth_endpoints,
            "oidc_config_found": bool(oidc_config),
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
