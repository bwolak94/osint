"""Encryption Sandbox — analyses TLS/SSL cipher suites and certificate properties.

Module 94 in the Infrastructure & Exploitation domain. Connects to the target
domain/URL over TLS and inspects the negotiated cipher suite, TLS protocol version,
certificate validity, subject, issuer, expiration, and supported algorithms.
Flags weak ciphers (RC4, DES, NULL, EXPORT), outdated TLS versions (SSLv2, SSLv3,
TLS 1.0, TLS 1.1), and certificate issues (expiry, self-signed, wildcard overuse).
"""

from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_WEAK_CIPHER_KEYWORDS = ["RC4", "DES", "NULL", "EXPORT", "anon", "MD5", "RC2", "SEED", "IDEA"]
_WEAK_TLS_VERSIONS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1", "TLS 1.0", "TLS 1.1"}


def _extract_host_port(input_value: str) -> tuple[str, int]:
    """Extract host and port from a domain or URL."""
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    host = parsed.hostname or parsed.netloc.split(":")[0]
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def _classify_cipher(cipher_name: str) -> dict[str, Any]:
    """Classify a cipher suite as strong, weak, or critical."""
    is_weak = any(kw in cipher_name for kw in _WEAK_CIPHER_KEYWORDS)
    is_forward_secret = "ECDHE" in cipher_name or "DHE" in cipher_name
    is_aead = "GCM" in cipher_name or "CCM" in cipher_name or "CHACHA20" in cipher_name

    if is_weak:
        strength = "Weak"
        risk = "High"
    elif is_forward_secret and is_aead:
        strength = "Strong"
        risk = "None"
    elif is_forward_secret or is_aead:
        strength = "Acceptable"
        risk = "Low"
    else:
        strength = "Moderate"
        risk = "Medium"

    return {
        "cipher": cipher_name,
        "strength": strength,
        "forward_secrecy": is_forward_secret,
        "aead": is_aead,
        "risk": risk,
    }


def _get_tls_info(host: str, port: int) -> dict[str, Any]:
    """Connect to the host over TLS and extract cipher/certificate details."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    result: dict[str, Any] = {
        "connected": False,
        "tls_version": "",
        "cipher_suite": "",
        "cipher_bits": 0,
        "cipher_classification": {},
        "certificate": {},
        "tls_issues": [],
        "cert_issues": [],
    }

    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                result["connected"] = True
                tls_version = ssock.version() or ""
                cipher = ssock.cipher()
                result["tls_version"] = tls_version
                result["cipher_suite"] = cipher[0] if cipher else ""
                result["cipher_bits"] = cipher[2] if cipher else 0
                result["cipher_classification"] = _classify_cipher(result["cipher_suite"])

                # TLS version checks
                if tls_version in _WEAK_TLS_VERSIONS:
                    result["tls_issues"].append(f"Outdated TLS version: {tls_version}")

                # Certificate details
                cert = ssock.getpeercert()
                if cert:
                    subject = dict(x[0] for x in cert.get("subject", []))
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    not_after_str = cert.get("notAfter", "")
                    not_before_str = cert.get("notBefore", "")

                    result["certificate"] = {
                        "subject_cn": subject.get("commonName", ""),
                        "issuer_cn": issuer.get("commonName", ""),
                        "issuer_org": issuer.get("organizationName", ""),
                        "not_before": not_before_str,
                        "not_after": not_after_str,
                        "san": [san[1] for san in cert.get("subjectAltName", [])],
                        "serial_number": cert.get("serialNumber", ""),
                        "version": cert.get("version", ""),
                    }

                    # Certificate expiry check
                    try:
                        not_after = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
                        not_after = not_after.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        days_remaining = (not_after - now).days
                        result["certificate"]["days_until_expiry"] = days_remaining
                        if days_remaining < 0:
                            result["cert_issues"].append(f"Certificate EXPIRED {abs(days_remaining)} days ago.")
                        elif days_remaining < 30:
                            result["cert_issues"].append(f"Certificate expires in {days_remaining} days — renewal urgent.")
                        elif days_remaining < 90:
                            result["cert_issues"].append(f"Certificate expires in {days_remaining} days.")
                    except ValueError:
                        pass

                    # Self-signed check
                    if subject.get("commonName") == issuer.get("commonName"):
                        result["cert_issues"].append("Potentially self-signed certificate.")

                    # Wildcard check
                    cn = subject.get("commonName", "")
                    sans = result["certificate"]["san"]
                    wildcard_count = sum(1 for s in [cn] + sans if s.startswith("*."))
                    if wildcard_count > 2:
                        result["cert_issues"].append(f"Excessive wildcard SANs ({wildcard_count}) — broad certificate scope.")

    except ssl.SSLError as exc:
        result["tls_issues"].append(f"SSL Error: {str(exc)}")
    except (socket.timeout, OSError) as exc:
        result["tls_issues"].append(f"Connection error: {str(exc)}")

    return result


class EncryptionSandboxScanner(BaseOsintScanner):
    """Analyses TLS/SSL configuration of the target domain.

    Connects over TLS and inspects the negotiated cipher suite, TLS protocol
    version, forward secrecy support, AEAD mode, and certificate properties.
    Flags weak ciphers, outdated protocols, and certificate issues (Module 94).
    """

    scanner_name = "encryption_sandbox"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host, port = _extract_host_port(input_value)

        loop = asyncio.get_event_loop()
        tls_info = await loop.run_in_executor(None, _get_tls_info, host, port)

        all_issues = tls_info.get("tls_issues", []) + tls_info.get("cert_issues", [])
        cipher_risk = tls_info.get("cipher_classification", {}).get("risk", "None")

        severity = "None"
        if any("EXPIRED" in i or "SSL Error" in i for i in all_issues):
            severity = "Critical"
        elif any("Outdated" in i or "Weak" in cipher_risk for i in all_issues) or cipher_risk == "High":
            severity = "High"
        elif all_issues:
            severity = "Medium"
        elif cipher_risk == "Medium":
            severity = "Medium"

        return {
            "target": host,
            "port": port,
            "found": tls_info.get("connected", False),
            "tls_version": tls_info.get("tls_version", ""),
            "cipher_suite": tls_info.get("cipher_suite", ""),
            "cipher_bits": tls_info.get("cipher_bits", 0),
            "cipher_analysis": tls_info.get("cipher_classification", {}),
            "certificate": tls_info.get("certificate", {}),
            "tls_issues": tls_info.get("tls_issues", []),
            "cert_issues": tls_info.get("cert_issues", []),
            "all_issues": all_issues,
            "issue_count": len(all_issues),
            "severity": severity,
            "educational_note": (
                "TLS misconfiguration allows downgrade attacks (POODLE, BEAST, DROWN), "
                "cipher suite weaknesses enable traffic decryption, and expired certificates "
                "break trust chains. Always use TLS 1.2+ with AEAD cipher suites."
            ),
            "recommendations": [
                "Disable TLS 1.0 and TLS 1.1; require TLS 1.2 minimum (TLS 1.3 preferred).",
                "Use only ECDHE or DHE key exchange for forward secrecy.",
                "Prefer AES-GCM or ChaCha20-Poly1305 (AEAD) cipher suites.",
                "Monitor certificate expiry and automate renewal with Let's Encrypt/ACME.",
                "Test configuration with SSL Labs (ssllabs.com/ssltest/).",
            ],
        }
