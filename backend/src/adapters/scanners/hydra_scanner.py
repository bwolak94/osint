"""Hydra — multi-protocol network login brute-force scanner.

THC-Hydra is the fastest and most flexible online password cracker.
Supports HTTP-Form, HTTP-Basic, FTP, SSH, SMTP, POP3, IMAP, and more.

Two-mode operation:
1. **hydra binary** — if on PATH, invoked for targeted credential testing
2. **Manual fallback** — HTTP authentication checks (Basic, form, default creds)
"""

from __future__ import annotations

import asyncio
import re
import shutil
from base64 import b64encode
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Top 20 most commonly used default credentials
_DEFAULT_CREDENTIALS: list[tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "123456"),
    ("admin", ""),
    ("root", "root"),
    ("root", "password"),
    ("root", ""),
    ("administrator", "administrator"),
    ("administrator", "password"),
    ("test", "test"),
    ("guest", "guest"),
    ("user", "user"),
    ("admin", "admin123"),
    ("admin", "1234"),
    ("admin", "12345"),
    ("admin", "pass"),
    ("admin", "letmein"),
    ("admin", "qwerty"),
    ("support", "support"),
    ("demo", "demo"),
]

# Common admin login paths to check
_LOGIN_PATHS: list[str] = [
    "/admin",
    "/admin/login",
    "/administrator",
    "/wp-login.php",
    "/login",
    "/signin",
    "/auth/login",
    "/user/login",
    "/panel",
    "/dashboard",
    "/cpanel",
    "/manager",
    "/console",
    "/admin.php",
    "/login.php",
]

# Services supporting HTTP Basic Auth — check headers
_BASIC_AUTH_INDICATORS = [
    "www-authenticate",
    "authorization",
]


class HydraScanner(BaseOsintScanner):
    """Network login brute-force and default credential scanner.

    Detects weak/default credentials on:
    - HTTP Basic Authentication endpoints
    - Web login forms (POST-based)
    - Admin panels with predictable locations
    Flags open/unauthenticated admin paths and default credential exposures.
    """

    scanner_name = "hydra"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("hydra"):
            return await self._run_hydra_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_hydra_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        scheme = parsed.scheme

        # Hydra HTTP-GET Basic auth test with default creds
        cmd = [
            "hydra",
            "-L", "/dev/stdin",
            "-P", "/dev/stdin",
            "-f",
            "-t", "4",
            "-w", "3",
            f"{scheme}-get://{host}/",
        ]
        # We run hydra in basic-auth mode against the host
        # Build user:pass list from defaults
        credentials_found: list[dict[str, Any]] = []

        try:
            proc = await asyncio.create_subprocess_exec(
                "hydra",
                "-C", "/usr/share/seclists/Passwords/Default-Credentials/default-passwords.csv",
                "-f", "-t", "4",
                f"{scheme}-get://{host}/",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.scan_timeout - 10)
                output = stdout.decode(errors="replace")
                for match in re.finditer(r"\[.*?\] host: (\S+)\s+login: (\S+)\s+password: (\S+)", output):
                    credentials_found.append({
                        "host": match.group(1),
                        "login": match.group(2),
                        "password": match.group(3),
                        "severity": "critical",
                    })
            except asyncio.TimeoutError:
                log.warning("hydra timed out", host=host)
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception as exc:
            log.debug("hydra binary failed", error=str(exc))

        identifiers = [f"credential:{c['login']}:{c['host']}" for c in credentials_found]
        return {
            "input": input_value,
            "scan_mode": "hydra_binary",
            "base_url": base_url,
            "credentials_found": credentials_found,
            "total_found": len(credentials_found),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        basic_auth_endpoints: list[str] = []
        open_admin_paths: list[str] = []
        default_cred_hits: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CredScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            # 1. Scan for admin paths and Basic Auth endpoints
            async def check_path(path: str) -> None:
                async with semaphore:
                    try:
                        url = base_url.rstrip("/") + path
                        resp = await client.get(url)

                        # HTTP Basic Auth challenge
                        if resp.status_code == 401 and "www-authenticate" in resp.headers:
                            auth_header = resp.headers["www-authenticate"]
                            basic_auth_endpoints.append(url)
                            findings.append({
                                "type": "basic_auth_endpoint",
                                "url": url,
                                "challenge": auth_header,
                                "severity": "medium",
                                "description": f"HTTP Basic Auth at {path}",
                            })
                            identifiers.append(f"url:{url}")

                            # Test default credentials against Basic Auth
                            for username, password in _DEFAULT_CREDENTIALS[:10]:
                                try:
                                    creds = b64encode(f"{username}:{password}".encode()).decode()
                                    auth_resp = await client.get(
                                        url,
                                        headers={"Authorization": f"Basic {creds}"},
                                    )
                                    if auth_resp.status_code in (200, 302, 301):
                                        default_cred_hits.append({
                                            "url": url,
                                            "username": username,
                                            "password": password,
                                            "severity": "critical",
                                        })
                                        identifiers.append(f"credential:{username}@{urlparse(url).hostname}")
                                        break
                                except Exception:
                                    pass

                        # Open admin panels (no auth)
                        elif resp.status_code == 200 and any(
                            kw in path for kw in ("/admin", "/panel", "/dashboard", "/console", "/manager")
                        ):
                            open_admin_paths.append(url)
                            findings.append({
                                "type": "open_admin_panel",
                                "url": url,
                                "status_code": resp.status_code,
                                "severity": "high",
                                "description": f"Admin panel accessible without authentication at {path}",
                            })
                            identifiers.append(f"url:{url}")

                    except Exception:
                        pass

            tasks = [check_path(p) for p in _LOGIN_PATHS]
            await asyncio.gather(*tasks)

            # 2. Detect login form and test default credentials
            try:
                resp = await client.get(base_url)
                if resp.status_code == 200:
                    body = resp.text
                    # Detect login form fields
                    has_password_field = bool(re.search(r'<input[^>]+type\s*=\s*["\']password["\']', body, re.I))
                    if has_password_field:
                        # Extract form action
                        form_match = re.search(r'<form[^>]*action\s*=\s*["\']([^"\']+)["\']', body, re.I)
                        form_action = form_match.group(1) if form_match else base_url
                        full_action = urljoin(base_url, form_action)

                        # Extract field names
                        user_field = "username"
                        pass_field = "password"
                        for field_pattern in [r'name\s*=\s*["\'](\w*user\w*)["\']', r'name\s*=\s*["\'](\w*login\w*)["\']']:
                            m = re.search(field_pattern, body, re.I)
                            if m:
                                user_field = m.group(1)
                                break
                        for field_pattern in [r'name\s*=\s*["\'](\w*pass\w*)["\']', r'name\s*=\s*["\'](\w*pwd\w*)["\']']:
                            m = re.search(field_pattern, body, re.I)
                            if m:
                                pass_field = m.group(1)
                                break

                        # Test top 5 default creds against the form
                        for username, password in _DEFAULT_CREDENTIALS[:5]:
                            try:
                                post_resp = await client.post(
                                    full_action,
                                    data={user_field: username, pass_field: password},
                                )
                                # Success indicators: redirect to dashboard, no "invalid" message
                                success_indicators = [
                                    post_resp.status_code in (301, 302),
                                    "dashboard" in post_resp.headers.get("location", "").lower(),
                                    "welcome" in post_resp.text.lower(),
                                    "logout" in post_resp.text.lower(),
                                ]
                                failure_indicators = [
                                    "invalid" in post_resp.text.lower(),
                                    "incorrect" in post_resp.text.lower(),
                                    "wrong" in post_resp.text.lower(),
                                    "error" in post_resp.text.lower(),
                                    "failed" in post_resp.text.lower(),
                                ]
                                if sum(success_indicators) >= 1 and sum(failure_indicators) == 0:
                                    default_cred_hits.append({
                                        "url": full_action,
                                        "username": username,
                                        "password": password,
                                        "method": "form_post",
                                        "severity": "critical",
                                    })
                                    identifiers.append(f"credential:{username}@{urlparse(base_url).hostname}")
                                    break
                            except Exception:
                                pass

            except Exception as exc:
                log.debug("Hydra form detection failed", url=base_url, error=str(exc))

        if default_cred_hits:
            findings.insert(0, {
                "type": "default_credentials",
                "severity": "critical",
                "description": f"Default credentials work: {len(default_cred_hits)} hit(s)",
                "hits": default_cred_hits,
            })

        severity_counts: dict[str, int] = {}
        for f in findings:
            s = f.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "findings": findings,
            "basic_auth_endpoints": basic_auth_endpoints,
            "open_admin_paths": open_admin_paths,
            "default_credential_hits": default_cred_hits,
            "total_findings": len(findings),
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
