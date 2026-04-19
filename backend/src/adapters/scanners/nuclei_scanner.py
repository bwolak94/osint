"""Nuclei vulnerability scanner — active misconfiguration and security-header checks."""

import asyncio
import hashlib
import json
import os
import shutil
import ssl
import socket
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SENSITIVE_PATHS = [
    ("/.git/HEAD", "exposed_git", "high"),
    ("/.env", "exposed_env_file", "critical"),
    ("/phpinfo.php", "exposed_phpinfo", "medium"),
    ("/info.php", "exposed_phpinfo", "medium"),
    ("/wp-admin/", "wordpress_admin_exposed", "info"),
    ("/wp-login.php", "wordpress_login_exposed", "low"),
    ("/admin/", "admin_panel_exposed", "info"),
    ("/administrator/", "admin_panel_exposed", "info"),
    ("/robots.txt", "robots_txt_present", "info"),
    ("/.DS_Store", "exposed_ds_store", "low"),
    ("/backup.zip", "exposed_backup_archive", "critical"),
    ("/backup.tar.gz", "exposed_backup_archive", "critical"),
]

_SECURITY_HEADERS = [
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]


class NucleiScanner(BaseOsintScanner):
    """Runs active web-application security checks against domains or URLs.

    Two-mode operation:
    1. **Nuclei binary** — if the ``nuclei`` executable is present on PATH,
       it is invoked with a 30-second timeout, severity filter
       (info/low/medium/high/critical), and JSON export.  Results from the
       JSON file are parsed and returned.
    2. **Manual checks** (fallback) — when the nuclei binary is not available
       the scanner performs lightweight HTTP-based checks:
       - Sensitive path enumeration (git, .env, backup files, admin panels)
       - HTTP security-header presence audit
       - Directory-listing detection ("Index of /")
       - SSL certificate expiry check (via stdlib ``ssl`` module)

    Input: DOMAIN or URL
    Returns:
    - vulnerabilities: list of findings with template_id, name, severity, matched_at
    - security_headers: dict mapping header name → present (bool)
    - misconfigurations: list of path-based findings
    - ssl_info: certificate subject, issuer, expiry date, days_until_expiry

    Each finding URL is surfaced as an extracted identifier.
    """

    scanner_name = "nuclei"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        if shutil.which("nuclei"):
            return await self._run_nuclei(base_url, input_value)
        return await self._manual_checks(base_url, input_value)

    # ------------------------------------------------------------------
    # Nuclei binary mode
    # ------------------------------------------------------------------

    async def _run_nuclei(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = hashlib.md5(input_value.encode()).hexdigest()[:12]
        json_export = os.path.join(tempfile.gettempdir(), f"nuclei_{run_id}.json")

        cmd = [
            "nuclei",
            "-u", base_url,
            "-severity", "info,low,medium,high,critical",
            "-silent",
            "-json-export", json_export,
            "-timeout", "30",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=60)
        except asyncio.TimeoutError:
            log.warning("Nuclei subprocess timed out", target=base_url)
            if proc.returncode is None:
                proc.kill()

        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        if os.path.exists(json_export):
            try:
                with open(json_export) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        finding = json.loads(line)
                        matched_at = finding.get("matched-at", base_url)
                        vulnerabilities.append({
                            "template_id": finding.get("template-id", ""),
                            "name": finding.get("info", {}).get("name", ""),
                            "severity": finding.get("info", {}).get("severity", "info"),
                            "matched_at": matched_at,
                            "description": finding.get("info", {}).get("description", ""),
                        })
                        ident = f"url:{matched_at}"
                        if ident not in identifiers:
                            identifiers.append(ident)
            except Exception as exc:
                log.warning("Failed to parse Nuclei JSON export", error=str(exc))
            finally:
                try:
                    os.unlink(json_export)
                except OSError:
                    pass

        return {
            "input": input_value,
            "scan_mode": "nuclei_binary",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "security_headers": {},
            "misconfigurations": [],
            "ssl_info": {},
            "extracted_identifiers": identifiers,
        }

    # ------------------------------------------------------------------
    # Manual fallback checks
    # ------------------------------------------------------------------

    async def _manual_checks(self, base_url: str, input_value: str) -> dict[str, Any]:
        misconfigurations: list[dict[str, Any]] = []
        identifiers: list[str] = []
        security_headers: dict[str, bool] = {}
        ssl_info: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,  # We check certs manually below
        ) as client:
            # 1. Security headers + directory-listing check on the root URL
            try:
                root_resp = await client.get(base_url)
                security_headers = _audit_security_headers(root_resp.headers)

                if "Index of /" in root_resp.text:
                    finding_url = str(root_resp.url)
                    misconfigurations.append({
                        "template_id": "directory-listing",
                        "name": "Directory listing enabled",
                        "severity": "medium",
                        "matched_at": finding_url,
                    })
                    ident = f"url:{finding_url}"
                    if ident not in identifiers:
                        identifiers.append(ident)
            except Exception as exc:
                log.debug("Root HTTP check failed", url=base_url, error=str(exc))

            # 2. Sensitive path checks
            for path, template_id, severity in _SENSITIVE_PATHS:
                target = base_url.rstrip("/") + path
                try:
                    resp = await client.get(target)
                    if resp.status_code in (200, 301, 302):
                        # robots.txt is normal — only flag if it reveals sensitive paths
                        if template_id == "robots_txt_present":
                            sensitive_keywords = ("admin", "backup", "config", "secret", "private")
                            if not any(kw in resp.text.lower() for kw in sensitive_keywords):
                                continue
                        misconfigurations.append({
                            "template_id": template_id,
                            "name": _template_to_name(template_id),
                            "severity": severity,
                            "matched_at": target,
                            "status_code": resp.status_code,
                        })
                        ident = f"url:{target}"
                        if ident not in identifiers:
                            identifiers.append(ident)
                except Exception:
                    pass  # Connection errors are expected for non-existent paths

        # 3. SSL certificate check
        hostname = _extract_hostname(base_url)
        if hostname:
            ssl_info = _check_ssl_cert(hostname)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": [],
            "security_headers": security_headers,
            "misconfigurations": misconfigurations,
            "ssl_info": ssl_info,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalise_url(value: str, input_type: ScanInputType) -> str:
    """Ensure the value is a fully qualified URL with scheme."""
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def _extract_hostname(url: str) -> str:
    """Parse the hostname from a URL string."""
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _audit_security_headers(headers: httpx.Headers) -> dict[str, bool]:
    """Return a dict of header_name → is_present for each security header."""
    normalised = {k.lower(): v for k, v in headers.items()}
    return {h: h.lower() in normalised for h in _SECURITY_HEADERS}


def _template_to_name(template_id: str) -> str:
    return template_id.replace("_", " ").title()


def _check_ssl_cert(hostname: str, port: int = 443) -> dict[str, Any]:
    """Retrieve and parse the SSL certificate for the given hostname."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.create_connection((hostname, port), timeout=5),
            server_hostname=hostname,
        ) as ssock:
            cert = ssock.getpeercert()

        not_after_str = cert.get("notAfter", "")
        expiry_dt: datetime | None = None
        days_until_expiry: int | None = None
        if not_after_str:
            expiry_dt = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days_until_expiry = (expiry_dt - datetime.now(timezone.utc)).days

        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))

        return {
            "subject": subject,
            "issuer": issuer,
            "not_before": cert.get("notBefore"),
            "not_after": not_after_str,
            "days_until_expiry": days_until_expiry,
            "expired": days_until_expiry is not None and days_until_expiry < 0,
            "expiring_soon": days_until_expiry is not None and 0 <= days_until_expiry <= 30,
            "san": [v for _, v in cert.get("subjectAltName", [])],
        }
    except ssl.SSLCertVerificationError as exc:
        return {"error": f"SSL verification failed: {exc}", "expired": None}
    except Exception as exc:
        return {"error": str(exc)}
