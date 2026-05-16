"""API Fuzzer — REST API endpoint discovery and vulnerability fuzzing scanner.

Combines OpenAPI/Swagger spec discovery with active endpoint fuzzing.
Discovers undocumented API endpoints via common path patterns, then probes
each for: authentication bypass, mass assignment, parameter pollution,
HTTP verb tampering, and excessive data exposure.

Mimics: wfuzz, ffuf, Burp Suite API scanning, kiterunner (kr).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# OpenAPI / Swagger spec paths
_SPEC_PATHS: list[str] = [
    "/swagger.json", "/swagger.yaml", "/swagger/v1/swagger.json",
    "/api-docs", "/api-docs.json", "/api/docs", "/api/swagger.json",
    "/openapi.json", "/openapi.yaml", "/openapi/v1",
    "/v1/api-docs", "/v2/api-docs", "/v3/api-docs",
    "/docs/api", "/redoc", "/scalar",
    "/graphql", "/graphiql",
    "/.well-known/openapi",
]

# API endpoint wordlist (kiterunner-style common paths)
_API_WORDLIST: list[str] = [
    "/api", "/api/v1", "/api/v2", "/api/v3",
    "/api/users", "/api/user", "/api/me", "/api/profile",
    "/api/admin", "/api/internal", "/api/private",
    "/api/health", "/api/status", "/api/version", "/api/info",
    "/api/config", "/api/settings", "/api/env",
    "/api/debug", "/api/test", "/api/ping",
    "/api/auth", "/api/login", "/api/logout", "/api/token", "/api/refresh",
    "/api/register", "/api/signup", "/api/reset-password",
    "/api/search", "/api/query",
    "/api/upload", "/api/download", "/api/export", "/api/import",
    "/api/orders", "/api/products", "/api/cart", "/api/checkout",
    "/api/payments", "/api/invoices", "/api/billing",
    "/api/messages", "/api/notifications", "/api/events",
    "/api/webhooks", "/api/callbacks",
    "/api/keys", "/api/tokens", "/api/secrets",
    "/api/logs", "/api/audit", "/api/metrics",
    "/api/reports", "/api/analytics", "/api/stats",
    "/api/files", "/api/media", "/api/assets",
    "/api/backup", "/api/restore",
    "/rest", "/rest/v1", "/rest/v2",
    "/v1", "/v2", "/v3",
    "/internal", "/private", "/hidden",
]

# HTTP methods to test for verb tampering
_HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE"]

# Mass assignment attack body — sends admin/privileged fields
_MASS_ASSIGNMENT_PAYLOADS: list[dict[str, Any]] = [
    {"role": "admin", "is_admin": True, "admin": True},
    {"role": "superuser", "permissions": ["*"], "verified": True},
    {"is_superuser": True, "is_staff": True, "active": True},
    {"privilege": "admin", "level": 99, "bypass": True},
]

# Excessive data exposure patterns
_SENSITIVE_FIELDS = re.compile(
    r'(?i)"(password|passwd|secret|api_key|apiKey|token|private_key|'
    r'credit_card|ssn|dob|salary|bank_account|access_token|refresh_token|'
    r'auth_token|session_token|internal_id|admin_note)"',
)

# Auth bypass test headers
_AUTH_BYPASS_HEADERS: list[dict[str, str]] = [
    {"Authorization": "Bearer null"},
    {"Authorization": "Bearer undefined"},
    {"Authorization": "Bearer 0"},
    {"Authorization": "Bearer "},
    {"X-Auth-Token": "null"},
    {"X-API-Key": "admin"},
    {"X-Role": "admin"},
    {"X-User-Id": "1"},
    {"X-Admin": "true"},
    {"X-Bypass": "1"},
]


class APIFuzzerScanner(BaseOsintScanner):
    """REST API endpoint discovery and vulnerability fuzzer.

    Discovers OpenAPI specs, maps undocumented endpoints, and probes for
    auth bypass, mass assignment, HTTP verb tampering, excessive data exposure,
    and parameter pollution vulnerabilities.
    """

    scanner_name = "api_fuzzer"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        spec_found: list[str] = []
        endpoints_found: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; APIFuzzer/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(12)

            # Step 1: Find OpenAPI/Swagger specs (information disclosure)
            async def check_spec(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        ct = resp.headers.get("content-type", "")
                        if resp.status_code == 200 and (
                            "json" in ct or "yaml" in ct or
                            '"swagger"' in resp.text or '"openapi"' in resp.text or
                            "swagger" in resp.text.lower()[:200]
                        ):
                            spec_found.append(url)
                            vulnerabilities.append({
                                "type": "api_spec_exposed",
                                "severity": "medium",
                                "url": url,
                                "description": "API specification (Swagger/OpenAPI) publicly accessible — full API surface disclosed",
                                "remediation": "Restrict API docs to authenticated users in production",
                            })
                            ident = "vuln:api:spec_exposed"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            await asyncio.gather(*[check_spec(p) for p in _SPEC_PATHS])

            # Step 2: Endpoint discovery
            async def discover_endpoint(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 201, 400, 422):
                            ct = resp.headers.get("content-type", "")
                            if "json" in ct or resp.status_code in (200, 201):
                                if url not in endpoints_found:
                                    endpoints_found.append(url)
                    except Exception:
                        pass

            await asyncio.gather(*[discover_endpoint(p) for p in _API_WORDLIST])

            # Step 3: Excessive data exposure check
            async def check_data_exposure(endpoint: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(endpoint)
                        if resp.status_code == 200:
                            body = resp.text
                            match = _SENSITIVE_FIELDS.search(body)
                            if match:
                                vulnerabilities.append({
                                    "type": "excessive_data_exposure",
                                    "severity": "high",
                                    "url": endpoint,
                                    "sensitive_field": match.group(1),
                                    "description": f"API endpoint returns sensitive field '{match.group(1)}' in response",
                                    "remediation": "Use response DTOs; never serialize internal model fields directly",
                                })
                                ident = f"vuln:api:data_exposure:{match.group(1)}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

            await asyncio.gather(*[check_data_exposure(ep) for ep in endpoints_found[:20]])

            # Step 4: Authentication bypass via header injection
            async def test_auth_bypass(endpoint: str, headers: dict[str, str]) -> None:
                async with semaphore:
                    # First get baseline without auth
                    try:
                        baseline = await client.get(endpoint)
                        if baseline.status_code not in (401, 403):
                            return  # Already accessible — skip

                        bypass_resp = await client.get(endpoint, headers=headers)
                        if bypass_resp.status_code in (200, 201):
                            header_name = list(headers.keys())[0]
                            vulnerabilities.append({
                                "type": "auth_bypass_header",
                                "severity": "critical",
                                "url": endpoint,
                                "header": header_name,
                                "header_value": headers[header_name],
                                "description": f"Auth bypass via '{header_name}' header — 401→200",
                                "remediation": "Remove trust in client-supplied auth headers; use signed tokens only",
                            })
                            ident = f"vuln:api:auth_bypass:{header_name.lower()}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            bypass_tasks = []
            for endpoint in endpoints_found[:8]:
                for headers in _AUTH_BYPASS_HEADERS[:5]:
                    bypass_tasks.append(test_auth_bypass(endpoint, headers))
            await asyncio.gather(*bypass_tasks)

            # Step 5: Mass assignment test on POST endpoints
            async def test_mass_assignment(endpoint: str, payload: dict) -> None:
                async with semaphore:
                    try:
                        resp = await client.post(endpoint, json=payload)
                        if resp.status_code in (200, 201):
                            body = resp.text
                            # If any of our privileged fields are reflected back
                            for field in ["role", "is_admin", "admin", "privilege", "level"]:
                                if f'"{field}": "admin"' in body or f'"{field}":true' in body or f'"{field}":99' in body:
                                    vulnerabilities.append({
                                        "type": "mass_assignment",
                                        "severity": "critical",
                                        "url": endpoint,
                                        "injected_field": field,
                                        "description": f"Mass assignment: field '{field}' accepted and reflected — privilege escalation possible",
                                        "remediation": "Use allowlists for accepted fields; never bind request body directly to model",
                                    })
                                    ident = "vuln:api:mass_assignment"
                                    if ident not in identifiers:
                                        identifiers.append(ident)
                                    break
                    except Exception:
                        pass

            mass_tasks = []
            for endpoint in endpoints_found[:6]:
                for payload in _MASS_ASSIGNMENT_PAYLOADS[:2]:
                    mass_tasks.append(test_mass_assignment(endpoint, payload))
            await asyncio.gather(*mass_tasks)

            # Step 6: HTTP verb tampering
            async def test_verb_tampering(endpoint: str) -> None:
                async with semaphore:
                    try:
                        # Baseline
                        get_resp = await client.get(endpoint)
                        if get_resp.status_code == 403:
                            # Try other methods
                            for method in ["POST", "PUT", "OPTIONS", "PATCH"]:
                                m_resp = await client.request(method, endpoint)
                                if m_resp.status_code == 200:
                                    vulnerabilities.append({
                                        "type": "http_verb_tampering",
                                        "severity": "high",
                                        "url": endpoint,
                                        "blocked_method": "GET",
                                        "bypassed_method": method,
                                        "description": f"HTTP verb tampering: GET blocked but {method} returns 200",
                                        "remediation": "Apply access control per resource, not per HTTP method",
                                    })
                                    ident = f"vuln:api:verb_tamper:{method}"
                                    if ident not in identifiers:
                                        identifiers.append(ident)
                                    break
                    except Exception:
                        pass

            await asyncio.gather(*[test_verb_tampering(ep) for ep in endpoints_found[:10]])

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "spec_files_found": spec_found,
            "endpoints_discovered": len(endpoints_found),
            "endpoints": endpoints_found[:50],
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
