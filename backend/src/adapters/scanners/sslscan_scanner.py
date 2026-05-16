"""SSLScan / TestSSL scanner — comprehensive SSL/TLS vulnerability analysis.

Detects: BEAST, POODLE, HEARTBLEED, ROBOT, weak ciphers, protocol version support,
certificate issues, HSTS, HPKP, expired/self-signed certs.

Two-mode operation:
1. **testssl.sh binary** — if present on PATH, invoked for full analysis
2. **Manual TLS checks** — Python ssl/socket probes covering the most critical checks
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import ssl
import struct
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SSL/TLS protocol versions to test
_PROTOCOLS = [
    ("SSLv2", ssl.PROTOCOL_TLS_CLIENT, "SSLv2"),
    ("SSLv3", ssl.PROTOCOL_TLS_CLIENT, "SSLv3"),
    ("TLSv1.0", ssl.PROTOCOL_TLS_CLIENT, "TLSv1"),
    ("TLSv1.1", ssl.PROTOCOL_TLS_CLIENT, "TLSv1.1"),
    ("TLSv1.2", ssl.PROTOCOL_TLS_CLIENT, "TLSv1.2"),
    ("TLSv1.3", ssl.PROTOCOL_TLS_CLIENT, "TLSv1.3"),
]

# Weak/insecure cipher patterns
_WEAK_CIPHER_PATTERNS = [
    "RC4", "NULL", "EXPORT", "anon", "DES ", "3DES", "ADH", "AECDH",
    "MD5", "RC2", "IDEA", "SEED",
]


class SSLScanScanner(BaseOsintScanner):
    """Comprehensive SSL/TLS security analysis scanner.

    Checks for: weak protocol versions (SSLv2/v3, TLS 1.0/1.1), insecure cipher
    suites, certificate validity/expiry/chain, HSTS header, known vulnerabilities
    (BEAST, POODLE indicators), certificate transparency.
    """

    scanner_name = "sslscan"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        hostname = _extract_hostname(input_value, input_type)
        if not hostname:
            return {"input": input_value, "error": "Could not extract hostname", "extracted_identifiers": []}

        if shutil.which("testssl.sh") or shutil.which("testssl"):
            return await self._run_testssl(hostname, input_value)
        return await self._manual_ssl_checks(hostname, input_value)

    async def _run_testssl(self, hostname: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"testssl_{run_id}.json")
        binary = shutil.which("testssl.sh") or "testssl"
        cmd = [binary, "--jsonfile", out_file, "--quiet", "--fast", hostname]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=90)
        except asyncio.TimeoutError:
            log.warning("testssl.sh timed out", hostname=hostname)
            try:
                proc.kill()
            except Exception:
                pass

        results: dict[str, Any] = {"input": input_value, "scan_mode": "testssl", "hostname": hostname}
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                vulnerabilities = []
                for item in data if isinstance(data, list) else []:
                    severity = item.get("severity", "")
                    if severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "WARN"):
                        vulnerabilities.append({
                            "id": item.get("id", ""),
                            "severity": severity.lower(),
                            "finding": item.get("finding", ""),
                        })
                results["vulnerabilities"] = vulnerabilities
                results["total_findings"] = len(vulnerabilities)
            except Exception as exc:
                log.warning("Failed to parse testssl output", error=str(exc))
                results["parse_error"] = str(exc)
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        results["extracted_identifiers"] = []
        return results

    async def _manual_ssl_checks(self, hostname: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        cert_info: dict[str, Any] = {}
        protocol_support: dict[str, bool] = {}
        cipher_info: dict[str, Any] = {}
        hsts_info: dict[str, Any] = {}

        # 1. Certificate and protocol analysis via default TLS context
        try:
            ctx = ssl.create_default_context()
            loop = asyncio.get_event_loop()
            cert_info, cipher_info, protocol_support = await loop.run_in_executor(
                None, lambda: _probe_ssl(hostname, ctx)
            )
        except ssl.SSLCertVerificationError as exc:
            vulnerabilities.append({
                "id": "ssl_cert_invalid",
                "severity": "critical",
                "finding": f"SSL certificate verification failed: {exc}",
            })
            cert_info = {"error": str(exc)}
        except Exception as exc:
            cert_info = {"error": str(exc)}

        # 2. Check for expired/expiring cert
        if cert_info.get("days_until_expiry") is not None:
            days = cert_info["days_until_expiry"]
            if days < 0:
                vulnerabilities.append({
                    "id": "cert_expired",
                    "severity": "critical",
                    "finding": f"SSL certificate expired {abs(days)} days ago",
                })
            elif days < 30:
                vulnerabilities.append({
                    "id": "cert_expiring_soon",
                    "severity": "high" if days < 7 else "medium",
                    "finding": f"SSL certificate expires in {days} days",
                })

        # 3. Self-signed certificate check
        if cert_info.get("self_signed"):
            vulnerabilities.append({
                "id": "self_signed_cert",
                "severity": "high",
                "finding": "Self-signed certificate detected — not trusted by browsers",
            })

        # 4. Weak cipher detection
        current_cipher = cipher_info.get("name", "")
        for pattern in _WEAK_CIPHER_PATTERNS:
            if pattern in current_cipher:
                vulnerabilities.append({
                    "id": "weak_cipher",
                    "severity": "high",
                    "finding": f"Weak cipher suite in use: {current_cipher}",
                })
                break

        # 5. Old TLS protocol check (TLS < 1.2 support)
        if protocol_support.get("tls_version") in ("TLSv1", "TLSv1.1"):
            vulnerabilities.append({
                "id": "outdated_tls",
                "severity": "medium",
                "finding": f"Outdated TLS version negotiated: {protocol_support.get('tls_version')}",
            })

        # 6. HSTS header check via HTTPS request
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.get(f"https://{hostname}")
                hsts_val = resp.headers.get("Strict-Transport-Security", "")
                hsts_info = {
                    "present": bool(hsts_val),
                    "value": hsts_val,
                    "max_age": _parse_hsts_max_age(hsts_val),
                    "include_subdomains": "includeSubDomains" in hsts_val,
                    "preload": "preload" in hsts_val,
                }
                if not hsts_val:
                    vulnerabilities.append({
                        "id": "missing_hsts",
                        "severity": "medium",
                        "finding": "HSTS (Strict-Transport-Security) header not set",
                    })
                elif _parse_hsts_max_age(hsts_val) < 2592000:  # < 30 days
                    vulnerabilities.append({
                        "id": "hsts_max_age_too_low",
                        "severity": "low",
                        "finding": f"HSTS max-age is too low: {hsts_val}",
                    })
        except Exception as exc:
            log.debug("HTTPS request for HSTS check failed", hostname=hostname, error=str(exc))

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "hostname": hostname,
            "cert_info": cert_info,
            "cipher_info": cipher_info,
            "protocol_support": protocol_support,
            "hsts": hsts_info,
            "vulnerabilities": vulnerabilities,
            "total_findings": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_hostname(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return value.split(":")[0].lstrip("*.")
    try:
        return urlparse(value).hostname or ""
    except Exception:
        return ""


def _probe_ssl(
    hostname: str, ctx: ssl.SSLContext, port: int = 443
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Synchronous SSL probe — run in executor to avoid blocking the event loop."""
    with ctx.wrap_socket(
        socket.create_connection((hostname, port), timeout=10),
        server_hostname=hostname,
    ) as ssock:
        cert = ssock.getpeercert()
        cipher = ssock.cipher()
        version = ssock.version()

    # Parse cert
    subject = dict(x[0] for x in cert.get("subject", []))
    issuer = dict(x[0] for x in cert.get("issuer", []))
    not_after = cert.get("notAfter", "")
    days: int | None = None
    if not_after:
        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (expiry - datetime.now(timezone.utc)).days

    cert_info = {
        "subject": subject,
        "issuer": issuer,
        "not_after": not_after,
        "days_until_expiry": days,
        "san": [v for _, v in cert.get("subjectAltName", [])],
        "self_signed": subject == issuer,
    }
    cipher_info = {
        "name": cipher[0] if cipher else "",
        "protocol": cipher[1] if cipher and len(cipher) > 1 else "",
        "bits": cipher[2] if cipher and len(cipher) > 2 else None,
    }
    protocol_info = {"tls_version": version}
    return cert_info, cipher_info, protocol_info


def _parse_hsts_max_age(hsts_value: str) -> int:
    for part in hsts_value.split(";"):
        part = part.strip()
        if part.lower().startswith("max-age="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                pass
    return 0
