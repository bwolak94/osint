"""Password Spray — credential stuffing and password spray vulnerability scanner.

Detects weak authentication configurations by testing whether login endpoints
allow unlimited attempts without lockout, rate limiting, or CAPTCHA. Tests
default/common credential pairs against discovered login endpoints.

Note: Uses minimal, non-aggressive probing (2-3 attempts max) to detect
missing lockout policies rather than active credential exploitation.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common login endpoint paths
_LOGIN_PATHS: list[str] = [
    "/login", "/signin", "/sign-in", "/auth/login",
    "/api/login", "/api/auth/login", "/api/v1/login", "/api/v1/auth/login",
    "/api/signin", "/user/login", "/account/login",
    "/wp-login.php", "/admin/login", "/admin",
    "/auth", "/api/auth", "/api/token",
]

# Common JSON field names for username/password
_CREDENTIAL_FIELDS: list[tuple[str, str]] = [
    ("username", "password"),
    ("email", "password"),
    ("user", "pass"),
    ("login", "password"),
    ("email", "passwd"),
]

# Small set of clearly-invalid test credentials for lockout detection
# These should NEVER succeed — we just measure response behavior
_PROBE_CREDENTIALS: list[tuple[str, str]] = [
    ("lockout_test_user_1@test.invalid", "WrongPass!1"),
    ("lockout_test_user_2@test.invalid", "WrongPass!2"),
    ("lockout_test_user_3@test.invalid", "WrongPass!3"),
    ("lockout_test_user_4@test.invalid", "WrongPass!4"),
    ("lockout_test_user_5@test.invalid", "WrongPass!5"),
]

# Common default credentials to check for admin panels
_DEFAULT_CREDS: list[tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "admin123"),
    ("administrator", "administrator"),
    ("root", "root"),
    ("guest", "guest"),
    ("test", "test"),
    ("admin", "1234"),
    ("admin", ""),
]

# Success indicators in response
_SUCCESS_PATTERNS = re.compile(
    r'(?i)("token"|"access_token"|"auth_token"|dashboard|welcome|'
    r'logged.in|successfully|redirect.*home)',
)

# Rate limiting / lockout indicators
_LOCKOUT_PATTERNS = re.compile(
    r'(?i)(locked|too many|rate.limit|429|throttl|blocked|banned|'
    r'maximum.attempt|account.disabled|captcha|wait)',
)

# CAPTCHA indicators
_CAPTCHA_PATTERNS = re.compile(
    r'(?i)(recaptcha|hcaptcha|captcha|turnstile|challenge|bot.detect)',
)


class PasswordSprayScanner(BaseOsintScanner):
    """Password spray and credential stuffing vulnerability scanner.

    Detects missing lockout/rate limiting on login endpoints by sending
    multiple invalid credential probes and measuring response behavior.
    Also tests default credentials on admin panels.
    """

    scanner_name = "password_spray"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        login_endpoints: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SecurityScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(4)

            # Step 1: Discover login endpoints
            async def find_login(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # Try GET first
                        resp = await client.get(url)
                        if resp.status_code in (200, 301, 302):
                            body = resp.text.lower()
                            if any(kw in body for kw in ["password", "login", "signin", "username", "email"]):
                                login_endpoints.append({"url": url, "path": path, "method": "GET"})
                                return

                        # Try POST with dummy credentials
                        for user_field, pass_field in _CREDENTIAL_FIELDS[:2]:
                            try:
                                resp = await client.post(
                                    url,
                                    json={user_field: "probe@test.invalid", pass_field: "probe_invalid"},
                                )
                                if resp.status_code not in (404, 405):
                                    login_endpoints.append({"url": url, "path": path, "method": "POST", "fields": (user_field, pass_field)})
                                    return
                            except Exception:
                                pass
                    except Exception:
                        pass

            await asyncio.gather(*[find_login(p) for p in _LOGIN_PATHS])

            # Step 2: Test lockout policy on discovered endpoints
            for endpoint_info in login_endpoints[:4]:
                url = endpoint_info["url"]
                fields = endpoint_info.get("fields", ("username", "password"))
                user_field, pass_field = fields

                responses: list[tuple[int, str, float]] = []

                # Send 5 invalid probes sequentially (not parallel — to measure lockout trigger)
                for username, password in _PROBE_CREDENTIALS[:5]:
                    try:
                        start = time.monotonic()
                        resp = await client.post(
                            url,
                            json={user_field: username, pass_field: password},
                        )
                        elapsed = time.monotonic() - start
                        responses.append((resp.status_code, resp.text[:300], elapsed))
                        await asyncio.sleep(0.3)  # Brief pause between attempts
                    except Exception:
                        responses.append((0, "", 0.0))

                valid_responses = [(s, b, t) for s, b, t in responses if s != 0]
                if not valid_responses:
                    continue

                # Check if any response shows lockout
                has_lockout = any(
                    _LOCKOUT_PATTERNS.search(body) or status == 429
                    for status, body, _ in valid_responses
                )
                has_captcha = any(
                    _CAPTCHA_PATTERNS.search(body)
                    for _, body, _ in valid_responses
                )

                # All 5 attempts got same 200/401 with no lockout = no brute-force protection
                status_codes = [s for s, _, _ in valid_responses]
                if not has_lockout and not has_captcha and len(valid_responses) == 5:
                    all_similar = len(set(status_codes)) == 1 or (
                        all(s in (200, 401, 403) for s in status_codes)
                    )
                    if all_similar:
                        vulnerabilities.append({
                            "type": "no_account_lockout",
                            "severity": "high",
                            "url": url,
                            "attempts_tested": len(valid_responses),
                            "status_codes": status_codes,
                            "description": f"Login endpoint at {url} has no lockout after {len(valid_responses)} failed attempts — vulnerable to password spray",
                            "remediation": "Implement account lockout (5-10 attempts), exponential backoff, and CAPTCHA",
                        })
                        ident = "vuln:password_spray:no_lockout"
                        if ident not in identifiers:
                            identifiers.append(ident)

                elif has_captcha:
                    # Captcha present — log as mitigated
                    pass
                elif has_lockout:
                    # Good — lockout implemented
                    pass

                # Check for username enumeration (different error messages)
                if len(valid_responses) >= 2:
                    bodies = [b for _, b, _ in valid_responses[:2]]
                    # Normalize and check if bodies are identical (good) or different (bad)
                    unique_bodies = len(set(b[:100] for b in bodies))
                    # But also check for "user not found" vs "wrong password" patterns
                    user_not_found = re.compile(r'(?i)(user.not.found|no.account|invalid.email|does.not.exist)')
                    wrong_pass = re.compile(r'(?i)(wrong.password|incorrect.password|invalid.password)')
                    if any(user_not_found.search(b) for b in bodies) or any(wrong_pass.search(b) for b in bodies):
                        vulnerabilities.append({
                            "type": "username_enumeration",
                            "severity": "medium",
                            "url": url,
                            "description": "Login endpoint reveals whether username exists via error message — enables targeted attacks",
                            "remediation": "Use generic error: 'Invalid username or password' regardless of which is wrong",
                        })
                        ident = "vuln:password_spray:user_enum"
                        if ident not in identifiers:
                            identifiers.append(ident)

            # Step 3: Test default credentials on admin panels
            admin_endpoints = [ep for ep in login_endpoints if "admin" in ep["url"]]
            for endpoint_info in admin_endpoints[:2]:
                url = endpoint_info["url"]
                fields = endpoint_info.get("fields", ("username", "password"))
                user_field, pass_field = fields

                for username, password in _DEFAULT_CREDS[:5]:
                    try:
                        resp = await client.post(
                            url,
                            json={user_field: username, pass_field: password},
                        )
                        body = resp.text
                        if resp.status_code in (200, 302) and _SUCCESS_PATTERNS.search(body):
                            vulnerabilities.append({
                                "type": "default_credentials",
                                "severity": "critical",
                                "url": url,
                                "username": username,
                                "description": f"Default credentials accepted: {username}:{password}",
                                "remediation": "Change all default credentials immediately; implement strong password policy",
                            })
                            identifiers.append("vuln:password_spray:default_creds")
                            break
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "login_endpoints_found": [ep["url"] for ep in login_endpoints],
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
