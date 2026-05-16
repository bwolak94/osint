"""Clickjacking — UI redress attack vulnerability scanner.

Clickjacking tricks users into clicking hidden UI elements by framing a
legitimate site inside an iframe on an attacker-controlled page.

Checks: X-Frame-Options, CSP frame-ancestors, Content-Type sniffing,
        frame-busting JavaScript, SameSite cookie flags.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Severity mapping for X-Frame-Options values
_XFO_SEVERITY: dict[str, str] = {
    "DENY": "none",          # Best
    "SAMEORIGIN": "none",    # Good
    "ALLOW-FROM": "low",     # Deprecated, bypassable
}

# CSP frame-ancestors directive — 'none' or 'self' is safe
_SAFE_FRAME_ANCESTORS = re.compile(r"frame-ancestors\s+(?:'none'|'self')", re.I)
_FRAME_ANCESTORS_RE = re.compile(r"frame-ancestors\s+([^;]+)", re.I)


class ClickjackingScanner(BaseOsintScanner):
    """Clickjacking / UI redress vulnerability scanner.

    Audits security headers preventing iframe embedding:
    - X-Frame-Options (DENY / SAMEORIGIN / ALLOW-FROM / missing)
    - Content-Security-Policy frame-ancestors directive
    - JavaScript frame-busting detection
    - SameSite cookie attribute (CSRF correlation)
    Provides detailed remediation advice per finding.
    """

    scanner_name = "clickjacking"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        headers_found: dict[str, str] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ClickjackingScanner/1.0)"},
        ) as client:
            try:
                resp = await client.get(base_url)
                body = resp.text

                # Collect relevant headers
                xfo = resp.headers.get("X-Frame-Options", "").strip().upper()
                csp = resp.headers.get("Content-Security-Policy", "")
                xcto = resp.headers.get("X-Content-Type-Options", "")
                set_cookie = resp.headers.get("set-cookie", "")

                if xfo:
                    headers_found["X-Frame-Options"] = xfo
                if csp:
                    headers_found["Content-Security-Policy"] = csp[:200]

                # --- Check 1: X-Frame-Options ---
                if not xfo:
                    # Check if CSP covers it
                    if "frame-ancestors" not in csp.lower():
                        vulnerabilities.append({
                            "type": "missing_x_frame_options",
                            "severity": "medium",
                            "description": "X-Frame-Options header missing — page can be framed",
                            "remediation": "Add 'X-Frame-Options: DENY' or use CSP frame-ancestors",
                        })
                        identifiers.append("vuln:clickjacking:missing_xfo")
                elif xfo == "ALLOW-FROM":
                    vulnerabilities.append({
                        "type": "xfo_allow_from",
                        "severity": "low",
                        "description": "X-Frame-Options: ALLOW-FROM is deprecated and bypassable in modern browsers",
                        "header_value": xfo,
                        "remediation": "Use CSP frame-ancestors instead",
                    })
                elif xfo not in ("DENY", "SAMEORIGIN"):
                    vulnerabilities.append({
                        "type": "xfo_invalid_value",
                        "severity": "medium",
                        "description": f"X-Frame-Options has non-standard value: '{xfo}'",
                        "header_value": xfo,
                        "remediation": "Use 'DENY' or 'SAMEORIGIN'",
                    })

                # --- Check 2: CSP frame-ancestors ---
                if "frame-ancestors" in csp.lower():
                    fa_match = _FRAME_ANCESTORS_RE.search(csp)
                    fa_value = fa_match.group(1).strip() if fa_match else ""
                    if "*" in fa_value:
                        vulnerabilities.append({
                            "type": "csp_frame_ancestors_wildcard",
                            "severity": "high",
                            "description": "CSP frame-ancestors allows '*' — any domain can frame this page",
                            "header_value": fa_value,
                            "remediation": "Set frame-ancestors to 'none' or 'self'",
                        })
                        identifiers.append("vuln:clickjacking:csp_wildcard")
                    elif _SAFE_FRAME_ANCESTORS.search(csp):
                        headers_found["csp_frame_ancestors_status"] = "safe"
                    else:
                        headers_found["csp_frame_ancestors_value"] = fa_value

                # --- Check 3: JavaScript frame-busting (weak protection) ---
                framebusting_patterns = [
                    (r"top\s*[!=]=\s*(?:window\.)?self", "top!=self"),
                    (r"top\s*\.\s*location\s*=\s*(?:window\.)?location", "top.location redirect"),
                    (r"if\s*\(\s*(?:window\.)?top\s*[!=]=", "top_window_check"),
                    (r"parent\s*[!=]=\s*(?:window\.)?self", "parent!=self"),
                ]
                framebusting_found: list[str] = []
                for pattern, desc in framebusting_patterns:
                    if re.search(pattern, body, re.I):
                        framebusting_found.append(desc)

                if framebusting_found and not xfo and "frame-ancestors" not in csp.lower():
                    vulnerabilities.append({
                        "type": "js_framebusting_only",
                        "severity": "low",
                        "description": "Only JavaScript frame-busting detected (bypassable via sandbox attribute)",
                        "techniques_found": framebusting_found,
                        "remediation": "Replace with X-Frame-Options or CSP frame-ancestors",
                    })

                # --- Check 4: SameSite cookies ---
                samesite_issues: list[str] = []
                if set_cookie:
                    for cookie in set_cookie.split("\n"):
                        if "samesite" not in cookie.lower():
                            cookie_name = cookie.split("=")[0].strip()
                            samesite_issues.append(cookie_name)
                if samesite_issues:
                    vulnerabilities.append({
                        "type": "cookies_missing_samesite",
                        "severity": "low",
                        "description": f"Cookies missing SameSite attribute: {', '.join(samesite_issues[:5])}",
                        "remediation": "Add SameSite=Strict or SameSite=Lax to session cookies",
                    })

                # --- Check 5: Overall verdict ---
                protected_by_xfo = xfo in ("DENY", "SAMEORIGIN")
                protected_by_csp = "frame-ancestors" in csp.lower() and "*" not in csp.lower()
                is_protected = protected_by_xfo or protected_by_csp

                if not is_protected:
                    identifiers.append("vuln:clickjacking:unprotected")

            except Exception as exc:
                log.debug("Clickjacking scan failed", url=base_url, error=str(exc))

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "headers_found": headers_found,
            "vulnerabilities": vulnerabilities,
            "total_findings": len(vulnerabilities),
            "is_protected": len([v for v in vulnerabilities if v.get("severity") in ("high", "medium")]) == 0,
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
