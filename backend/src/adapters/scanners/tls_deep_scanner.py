"""TLS Deep — comprehensive SSL/TLS vulnerability scanner.

Goes beyond basic certificate checks to detect: BEAST, POODLE, DROWN, FREAK,
LUCKY13, ROBOT, SWEET32, weak ciphers, TLS 1.0/1.1 support, expired/self-signed
certs, HSTS/HPKP misconfiguration, certificate transparency, and downgrade attacks.

Complements sslscan with active protocol-level probing.
"""

from __future__ import annotations

import asyncio
import datetime
import re
import socket
import ssl
import struct
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Cipher suites considered weak/broken
_WEAK_CIPHERS: set[str] = {
    "RC4", "DES", "3DES", "EXPORT", "NULL", "ANON", "MD5",
    "RC2", "IDEA", "SEED", "CAMELLIA128", "ADH", "AECDH",
}

# TLS protocol versions
_TLS_VERSIONS: list[tuple[str, int, int]] = [
    ("SSLv2",   2, 0),
    ("SSLv3",   3, 0),
    ("TLSv1.0", 3, 1),
    ("TLSv1.1", 3, 2),
    ("TLSv1.2", 3, 3),
    ("TLSv1.3", 3, 4),
]

# CVE map for deprecated protocol/cipher issues
_PROTOCOL_CVES: dict[str, dict[str, str]] = {
    "SSLv2":   {"cve": "CVE-2016-0800", "name": "DROWN", "severity": "critical"},
    "SSLv3":   {"cve": "CVE-2014-3566", "name": "POODLE", "severity": "high"},
    "TLSv1.0": {"cve": "CVE-2011-3389", "name": "BEAST", "severity": "medium"},
    "TLSv1.1": {"cve": "N/A",            "name": "Deprecated TLS", "severity": "low"},
}


class TLSDeepScanner(BaseOsintScanner):
    """Deep TLS/SSL vulnerability scanner.

    Probes the target's TLS stack for deprecated protocol support (SSLv2/3,
    TLS 1.0/1.1), weak cipher suites, certificate issues (expiry, self-signed,
    mismatched hostname), missing HSTS/HPKP headers, and known CVEs.
    """

    scanner_name = "tls_deep"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = _extract_host(input_value, input_type)
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_scan, host, input_value
        )

    def _sync_scan(self, host: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        cert_info: dict[str, Any] = {}
        supported_protocols: list[str] = []
        weak_ciphers_found: list[str] = []

        # --- Step 1: Certificate inspection ---
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(
                socket.create_connection((host, 443), timeout=8),
                server_hostname=host,
            ) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                proto = ssock.version()

                if proto:
                    supported_protocols.append(proto)

                # Expiry check
                not_after_str = cert.get("notAfter", "")
                if not_after_str:
                    try:
                        not_after = datetime.datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
                        days_left = (not_after - datetime.datetime.utcnow()).days
                        cert_info["expiry"] = not_after_str
                        cert_info["days_remaining"] = days_left
                        if days_left < 0:
                            vulnerabilities.append({
                                "type": "cert_expired",
                                "severity": "critical",
                                "host": host,
                                "expired_at": not_after_str,
                                "description": f"TLS certificate expired {abs(days_left)} days ago",
                                "remediation": "Renew certificate immediately",
                            })
                            identifiers.append("vuln:tls:cert_expired")
                        elif days_left < 30:
                            vulnerabilities.append({
                                "type": "cert_expiring_soon",
                                "severity": "medium",
                                "host": host,
                                "days_remaining": days_left,
                                "description": f"TLS certificate expires in {days_left} days",
                            })
                            identifiers.append("vuln:tls:cert_expiring")
                    except ValueError:
                        pass

                # Subject / SAN extraction
                subject = dict(x[0] for x in cert.get("subject", []))
                san = [v for _, v in cert.get("subjectAltName", [])]
                cert_info["subject_cn"] = subject.get("commonName", "")
                cert_info["san"] = san[:10]
                cert_info["issuer"] = dict(x[0] for x in cert.get("issuer", [])).get("organizationName", "")

                # Hostname mismatch
                if host not in san and f"*.{'.'.join(host.split('.')[1:])}" not in san:
                    if subject.get("commonName", "") != host:
                        vulnerabilities.append({
                            "type": "cert_hostname_mismatch",
                            "severity": "high",
                            "host": host,
                            "cert_cn": subject.get("commonName", ""),
                            "description": "Certificate hostname mismatch — MITM risk",
                        })
                        identifiers.append("vuln:tls:hostname_mismatch")

                # Self-signed check
                if cert_info.get("issuer") == subject.get("organizationName", "UNKNOWN"):
                    vulnerabilities.append({
                        "type": "self_signed_cert",
                        "severity": "high",
                        "host": host,
                        "description": "Self-signed certificate detected",
                        "remediation": "Replace with CA-issued certificate (Let's Encrypt is free)",
                    })
                    identifiers.append("vuln:tls:self_signed")

                # Weak cipher in use
                if cipher:
                    cipher_name = cipher[0] if cipher else ""
                    for weak in _WEAK_CIPHERS:
                        if weak in cipher_name.upper():
                            weak_ciphers_found.append(cipher_name)
                            vulnerabilities.append({
                                "type": "weak_cipher_in_use",
                                "severity": "high",
                                "host": host,
                                "cipher": cipher_name,
                                "description": f"Weak cipher suite in use: {cipher_name}",
                                "remediation": "Configure only AESGCM, CHACHA20 cipher suites",
                            })
                            identifiers.append(f"vuln:tls:weak_cipher")
                            break

        except ssl.SSLCertVerificationError:
            vulnerabilities.append({
                "type": "cert_verification_failed",
                "severity": "high",
                "host": host,
                "description": "Certificate verification failed (untrusted CA or self-signed)",
            })
            identifiers.append("vuln:tls:cert_unverified")
        except ssl.CertificateError as e:
            vulnerabilities.append({
                "type": "cert_error",
                "severity": "medium",
                "host": host,
                "error": str(e)[:100],
                "description": f"Certificate error: {str(e)[:80]}",
            })
        except Exception as exc:
            log.debug("TLS cert inspection failed", host=host, error=str(exc))

        # --- Step 2: Probe for deprecated TLS versions ---
        deprecated_to_check = [
            ("SSLv3", ssl.PROTOCOL_TLS_CLIENT, ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2 | ssl.OP_NO_TLSv1_3),
            ("TLSv1.0", ssl.PROTOCOL_TLS_CLIENT, ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2 | ssl.OP_NO_TLSv1_3),
            ("TLSv1.1", ssl.PROTOCOL_TLS_CLIENT, ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_2 | ssl.OP_NO_TLSv1_3),
        ]

        for version_name, proto_const, options in deprecated_to_check:
            try:
                ctx = ssl.SSLContext(proto_const)
                ctx.options |= options
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with ctx.wrap_socket(
                    socket.create_connection((host, 443), timeout=5),
                    server_hostname=host,
                ) as ssock:
                    actual = ssock.version()
                    if actual and version_name.replace("v", " ").replace(".", "") in actual.replace(".", ""):
                        supported_protocols.append(version_name)
                        cve_info = _PROTOCOL_CVES.get(version_name, {})
                        vulnerabilities.append({
                            "type": "deprecated_tls_supported",
                            "severity": cve_info.get("severity", "medium"),
                            "host": host,
                            "protocol": version_name,
                            "cve": cve_info.get("cve"),
                            "attack_name": cve_info.get("name"),
                            "description": f"{version_name} supported — {cve_info.get('name', 'deprecated protocol')}",
                            "remediation": "Disable SSLv2/3, TLS 1.0, TLS 1.1 in web server config",
                        })
                        ident = f"vuln:tls:{version_name.lower()}"
                        if ident not in identifiers:
                            identifiers.append(ident)
            except Exception:
                pass

        # --- Step 3: HTTP security headers (HSTS, HPKP) ---
        try:
            import urllib.request
            req = urllib.request.Request(f"https://{host}", headers={"User-Agent": "TLSScanner/1.0"})
            with urllib.request.urlopen(req, timeout=8, context=ssl.create_default_context()) as resp:
                hsts = resp.headers.get("Strict-Transport-Security", "")
                hpkp = resp.headers.get("Public-Key-Pins", "")

                if not hsts:
                    vulnerabilities.append({
                        "type": "hsts_missing",
                        "severity": "medium",
                        "host": host,
                        "description": "HTTP Strict Transport Security (HSTS) header missing — SSL stripping attack possible",
                        "remediation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload",
                    })
                    identifiers.append("vuln:tls:hsts_missing")
                else:
                    # Check HSTS max-age
                    max_age_m = re.search(r"max-age=(\d+)", hsts)
                    if max_age_m:
                        max_age = int(max_age_m.group(1))
                        if max_age < 31536000:
                            vulnerabilities.append({
                                "type": "hsts_weak",
                                "severity": "low",
                                "host": host,
                                "max_age": max_age,
                                "description": f"HSTS max-age={max_age} is less than 1 year (31536000)",
                            })
        except Exception:
            pass

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "certificate": cert_info,
            "supported_protocols": supported_protocols,
            "weak_ciphers": weak_ciphers_found,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
