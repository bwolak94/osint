"""Host Header Injection — password reset poisoning and cache deception scanner.

Host header injection occurs when a server trusts the HTTP Host header to
generate links in emails (password reset, activation) or for routing. Attackers
can inject a malicious host to poison reset links, bypass access controls, or
cause web cache deception via X-Forwarded-Host / X-Host substitution.
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

# Canary domain for OOB detection (noted in results but not actively probed)
_CANARY_HOST = f"hhi-probe-{uuid.uuid4().hex[:8]}.evil.example.com"

# Host header injection payloads
_HOST_PAYLOADS: list[tuple[str, str]] = [
    (_CANARY_HOST, "direct_host_override"),
    (f"evil.com", "evil_host"),
    (f"localhost", "localhost_bypass"),
    (f"127.0.0.1", "loopback_bypass"),
    (f"evil.com:80@legit.com", "credential_host"),
    (f"evil.com #", "comment_injection"),
    (f"evil.com\r\n", "crlf_in_host"),
    (f"evil.com%0d%0a", "encoded_crlf_host"),
]

# Additional headers to inject evil host
_HOST_OVERRIDE_HEADERS: list[tuple[str, str]] = [
    ("X-Forwarded-Host", "evil.com"),
    ("X-Host", "evil.com"),
    ("X-Forwarded-Server", "evil.com"),
    ("X-HTTP-Host-Override", "evil.com"),
    ("Forwarded", "host=evil.com"),
    ("X-Original-Host", "evil.com"),
]

# Paths that commonly use Host header in generated URLs
_HOST_SENSITIVE_PATHS: list[str] = [
    "/forgot-password",
    "/password-reset",
    "/reset-password",
    "/auth/forgot",
    "/auth/reset",
    "/api/password-reset",
    "/api/v1/password-reset",
    "/api/forgot-password",
    "/account/recover",
    "/user/reset",
]


class HostHeaderInjectionScanner(BaseOsintScanner):
    """Host header injection / password reset poisoning scanner.

    Tests HTTP Host, X-Forwarded-Host, and related headers for reflection
    in responses, redirects, and password reset link generation. Identifies
    endpoints where Host header injection could poison reset emails.
    """

    scanner_name = "host_header_injection"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        original_host = urlparse(base_url).netloc

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HHIScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Test 1: Host header reflected in response
            async def test_host_reflection(path: str, host_value: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(
                            url,
                            headers={"Host": host_value},
                        )
                        body = resp.text
                        location = resp.headers.get("location", "")

                        # Check if injected host appears in response body
                        if "evil.com" in body or _CANARY_HOST in body:
                            vulnerabilities.append({
                                "type": "host_header_reflected_in_body",
                                "severity": "high",
                                "url": url,
                                "injected_host": host_value[:50],
                                "technique": technique,
                                "description": "Injected Host header value reflected in response body — password reset poisoning risk",
                                "remediation": "Hard-code the application domain; never use Host header to generate links",
                            })
                            ident = f"vuln:hhi:reflected:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Check redirect to injected host
                        if "evil.com" in location or _CANARY_HOST in location:
                            vulnerabilities.append({
                                "type": "host_header_redirect",
                                "severity": "high",
                                "url": url,
                                "injected_host": host_value[:50],
                                "redirect_location": location[:100],
                                "technique": technique,
                                "description": "Host header injection causes redirect to attacker-controlled domain",
                            })
                            ident = f"vuln:hhi:redirect:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            # Test 2: X-Forwarded-Host and override headers
            async def test_override_header(path: str, header: str, value: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(
                            url,
                            headers={
                                "Host": original_host,
                                header: value,
                            },
                        )
                        body = resp.text
                        location = resp.headers.get("location", "")

                        if "evil.com" in body or "evil.com" in location:
                            vulnerabilities.append({
                                "type": "host_override_header_reflected",
                                "severity": "high",
                                "url": url,
                                "header": header,
                                "injected_value": value,
                                "description": f"'{header}' override header reflected in response — server trusts proxy headers for URL generation",
                                "remediation": "Only trust X-Forwarded-Host from internal trusted proxies; use allowlist",
                            })
                            ident = f"vuln:hhi:override:{header.lower()}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            # Test 3: Password reset poisoning — POST with evil Host header
            async def test_reset_poisoning(path: str, host_value: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # Send POST to reset endpoint with injected Host
                        resp = await client.post(
                            url,
                            json={"email": "victim@target.example.com"},
                            headers={
                                "Host": host_value,
                                "Content-Type": "application/json",
                            },
                        )
                        body = resp.text
                        status = resp.status_code

                        # If 200/201 and no error = server accepted the request with evil Host
                        # This means reset links will contain evil.com
                        if status in (200, 201, 202):
                            if not re.search(r'(?i)(error|invalid|not.found|fail)', body):
                                vulnerabilities.append({
                                    "type": "password_reset_poisoning",
                                    "severity": "critical",
                                    "url": url,
                                    "injected_host": host_value[:50],
                                    "status_code": status,
                                    "description": "Password reset endpoint accepted request with injected Host header — reset links may point to attacker's domain",
                                    "cwe": "CWE-20",
                                    "remediation": "Hard-code the base URL for password reset links; never use request Host header",
                                })
                                ident = "vuln:hhi:password_reset_poison"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            tasks = []
            for path in _HOST_SENSITIVE_PATHS[:6]:
                for host_value, technique in _HOST_PAYLOADS[:4]:
                    tasks.append(test_host_reflection(path, host_value, technique))
                    tasks.append(test_reset_poisoning(path, "evil.com"))

            for header, value in _HOST_OVERRIDE_HEADERS[:4]:
                tasks.append(test_override_header("/", header, value))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "canary_host": _CANARY_HOST,
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
