"""CSRF — Cross-Site Request Forgery vulnerability scanner.

CSRF tricks authenticated users into performing unintended actions.
Tests for missing CSRF tokens, SameSite cookie bypass, Referer-only
protection, and JSON-based CSRF attacks.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# CSRF token field name patterns
_CSRF_FIELD_PATTERNS = re.compile(
    r'(?i)name=["\'](_?csrf|_?token|authenticity_token|__requestverificationtoken|'
    r'csrf_token|_csrf_token|xsrf_token|_xsrf|csrfmiddlewaretoken|__csrf)["\']'
)

# CSRF cookie patterns
_CSRF_COOKIE_PATTERNS = re.compile(
    r'(?i)(csrf|xsrf|_token|antiforgery)',
)

# Common form-submitting endpoints
_STATE_CHANGE_PATHS = [
    "/profile", "/account", "/settings", "/password",
    "/email", "/api/user", "/api/account", "/api/settings",
    "/admin", "/api/admin", "/api/v1/user",
    "/logout", "/delete", "/transfer",
]


class CSRFScanner(BaseOsintScanner):
    """Cross-Site Request Forgery (CSRF) vulnerability scanner.

    Detects:
    - Missing CSRF tokens on state-changing forms
    - SameSite cookie attribute absence
    - Referer-only CSRF protection (bypassable)
    - JSON content-type CSRF (no token required)
    - CORS + CSRF combined misconfigurations
    """

    scanner_name = "csrf"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        forms_analysed: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True, verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CSRFScanner/1.0)"},
        ) as client:
            try:
                resp = await client.get(base_url)
                body = resp.text
                set_cookie = resp.headers.get("set-cookie", "")

                # --- Check 1: Cookies missing SameSite ---
                samesite_missing: list[str] = []
                secure_missing: list[str] = []
                for cookie_line in set_cookie.split("\n"):
                    if not cookie_line.strip():
                        continue
                    name = cookie_line.split("=")[0].strip()
                    if "samesite" not in cookie_line.lower():
                        samesite_missing.append(name)
                    if "secure" not in cookie_line.lower():
                        secure_missing.append(name)

                if samesite_missing:
                    vulnerabilities.append({
                        "type": "samesite_missing",
                        "severity": "medium",
                        "cookies": samesite_missing[:5],
                        "description": "Cookies missing SameSite attribute — cross-origin requests send cookies",
                        "remediation": "Set SameSite=Strict or SameSite=Lax on all session cookies",
                    })
                    identifiers.append("vuln:csrf:samesite_missing")

                # --- Check 2: Extract and analyse forms ---
                form_pattern = re.compile(
                    r'<form([^>]*)>(.*?)</form>', re.DOTALL | re.I
                )
                for form_match in form_pattern.finditer(body):
                    form_attrs = form_match.group(1)
                    form_content = form_match.group(2)
                    method_m = re.search(r'method\s*=\s*["\'](\w+)["\']', form_attrs, re.I)
                    action_m = re.search(r'action\s*=\s*["\']([^"\']+)["\']', form_attrs, re.I)
                    method = (method_m.group(1) if method_m else "GET").upper()
                    action = action_m.group(1) if action_m else base_url
                    has_csrf_token = bool(_CSRF_FIELD_PATTERNS.search(form_content))
                    has_password = bool(re.search(r'type\s*=\s*["\']password["\']', form_content, re.I))
                    has_sensitive = bool(re.search(
                        r'(?i)(email|password|credit|card|transfer|amount|delete|admin)',
                        form_content,
                    ))

                    form_info = {
                        "action": urljoin(base_url, action),
                        "method": method,
                        "has_csrf_token": has_csrf_token,
                        "has_password_field": has_password,
                        "has_sensitive_fields": has_sensitive,
                    }
                    forms_analysed.append(form_info)

                    # Flag POST forms without CSRF token
                    if method == "POST" and not has_csrf_token and has_sensitive:
                        vulnerabilities.append({
                            "type": "missing_csrf_token",
                            "severity": "high",
                            "form_action": urljoin(base_url, action),
                            "description": "POST form with sensitive fields has no CSRF token",
                            "remediation": "Add CSRF token to all state-changing forms",
                        })
                        ident = "vuln:csrf:missing_token"
                        if ident not in identifiers:
                            identifiers.append(ident)

                # --- Check 3: Referer-only protection ---
                # Send a POST without Referer and check if it proceeds
                for path in _STATE_CHANGE_PATHS[:5]:
                    try:
                        no_ref_resp = await client.post(
                            base_url.rstrip("/") + path,
                            data={"test": "csrf_probe"},
                            headers={"Referer": ""},  # No referer
                        )
                        ref_resp = await client.post(
                            base_url.rstrip("/") + path,
                            data={"test": "csrf_probe"},
                            headers={"Referer": "https://evil.com"},  # Attacker referer
                        )
                        # Both succeed without CSRF token = vulnerable to CSRF
                        if ref_resp.status_code not in (403, 400) and ref_resp.status_code == no_ref_resp.status_code:
                            if ref_resp.status_code in (200, 302):
                                vulnerabilities.append({
                                    "type": "no_referer_check",
                                    "severity": "medium",
                                    "path": path,
                                    "description": "POST endpoint accepts cross-origin Referer without CSRF token",
                                })
                                ident = f"vuln:csrf:no_referer:{path}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

                # --- Check 4: JSON CSRF (no token in application/json) ---
                for path in _STATE_CHANGE_PATHS[:3]:
                    try:
                        json_resp = await client.post(
                            base_url.rstrip("/") + path,
                            json={"action": "test"},
                            headers={"Content-Type": "application/json", "Origin": "https://evil.com"},
                        )
                        if json_resp.status_code in (200, 201):
                            acao = json_resp.headers.get("Access-Control-Allow-Origin", "")
                            if acao in ("*", "https://evil.com"):
                                vulnerabilities.append({
                                    "type": "json_csrf_cors",
                                    "severity": "high",
                                    "path": path,
                                    "description": "JSON endpoint accepts cross-origin requests with permissive CORS",
                                })
                                identifiers.append("vuln:csrf:json_cors")
                    except Exception:
                        pass

            except Exception as exc:
                log.debug("CSRF scan failed", url=base_url, error=str(exc))

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "forms_analysed": len(forms_analysed),
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
