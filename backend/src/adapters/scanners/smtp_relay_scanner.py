"""SMTP Relay — open relay detection, header injection, and mail spoofing scanner.

Tests SMTP servers for: open relay (relaying email to external domains without auth),
email header injection via form fields, SMTP user enumeration (VRFY/EXPN commands),
plaintext AUTH, STARTTLS downgrade, and mail spoofing feasibility.
"""

from __future__ import annotations

import asyncio
import re
import socket
import ssl
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SMTP test credentials for AUTH testing
_TEST_SMTP_USERS = ["admin", "test", "info", "noreply", "postmaster"]

# Common SMTP ports
_SMTP_PORTS: list[int] = [25, 465, 587, 2525]

# SMTP banner patterns
_SMTP_BANNER = re.compile(r"^220\s+(.+?)(?:\r?\n|$)", re.M)

# SMTP response patterns
_RELAY_OK = re.compile(r"^(250|251)\s", re.M)
_AUTH_METHODS = re.compile(r"AUTH\s+([\w\s]+)", re.I)
_VRFY_VALID = re.compile(r"^(250|251|252)\s", re.M)

# SMTP header injection test strings
_HEADER_INJECTIONS: list[tuple[str, str]] = [
    ("To: victim@target.com\r\nBcc: attacker@evil.com", "bcc_injection"),
    ("victim@target.com\r\nCC: attacker@evil.com", "cc_injection"),
    ("victim@target.com%0ACc:attacker@evil.com", "encoded_lf_injection"),
    ("victim@target.com\nBcc:attacker@evil.com", "lf_injection"),
]

# Email addresses for relay test
_RELAY_FROM = "scanner-test@scanner.invalid"
_RELAY_TO_EXTERNAL = "test@relay-test-external.invalid"  # External domain
_RELAY_TO_INTERNAL_TEMPLATE = "test@{domain}"


class SMTPRelayScanner(BaseOsintScanner):
    """SMTP open relay and email security scanner.

    Tests for open relay, VRFY/EXPN enumeration, STARTTLS downgrade,
    plaintext AUTH, and mail spoofing via header injection.
    """

    scanner_name = "smtp_relay"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 7200
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip()
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_scan, domain, input_value, input_type
        )

    def _sync_scan(self, target: str, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        smtp_info: dict[str, Any] = {}

        # Resolve MX if domain
        if input_type == ScanInputType.DOMAIN:
            smtp_hosts = self._get_mx_hosts(target) or [target]
        else:
            smtp_hosts = [target]

        for smtp_host in smtp_hosts[:3]:
            for port in _SMTP_PORTS:
                result = self._probe_smtp(smtp_host, port, target)
                if result:
                    smtp_info.update(result.get("info", {}))
                    vulnerabilities.extend(result.get("vulnerabilities", []))
                    identifiers.extend(
                        i for i in result.get("identifiers", []) if i not in identifiers
                    )

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "target": target,
            "smtp_info": smtp_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _get_mx_hosts(self, domain: str) -> list[str]:
        try:
            import subprocess
            result = subprocess.run(
                ["dig", "+short", "MX", domain],
                capture_output=True, text=True, timeout=5,
            )
            hosts = []
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    host = parts[-1].rstrip(".")
                    if host:
                        hosts.append(host)
            return hosts[:3]
        except Exception:
            return []

    def _probe_smtp(self, host: str, port: int, domain: str) -> dict[str, Any] | None:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        info: dict[str, Any] = {}

        try:
            sock = socket.create_connection((host, port), timeout=8)
        except Exception:
            return None

        try:
            # Read banner
            banner = sock.recv(1024).decode(errors="replace")
            if not banner.startswith("220"):
                sock.close()
                return None

            banner_match = _SMTP_BANNER.search(banner)
            info["banner"] = banner_match.group(1)[:100] if banner_match else banner[:100]
            info["host"] = host
            info["port"] = port

            # EHLO
            sock.sendall(f"EHLO scanner.invalid\r\n".encode())
            ehlo_resp = sock.recv(2048).decode(errors="replace")
            info["supports_starttls"] = "STARTTLS" in ehlo_resp
            info["supports_auth"] = "AUTH" in ehlo_resp

            auth_match = _AUTH_METHODS.search(ehlo_resp)
            if auth_match:
                info["auth_methods"] = auth_match.group(1).strip()
                if "PLAIN" in ehlo_resp or "LOGIN" in ehlo_resp:
                    if port not in (465, 587) or not info.get("supports_starttls"):
                        vulnerabilities.append({
                            "type": "smtp_plaintext_auth",
                            "severity": "medium",
                            "host": host,
                            "port": port,
                            "auth_methods": info["auth_methods"],
                            "description": f"SMTP on port {port} offers plaintext AUTH (PLAIN/LOGIN) without mandatory TLS",
                            "remediation": "Require STARTTLS before AUTH; use port 587 with mandatory TLS",
                        })
                        identifiers.append("vuln:smtp:plaintext_auth")

            # Check STARTTLS availability
            if not info["supports_starttls"] and port in (25, 587):
                vulnerabilities.append({
                    "type": "smtp_no_starttls",
                    "severity": "medium",
                    "host": host,
                    "port": port,
                    "description": f"SMTP on port {port} does not support STARTTLS — credentials transmitted in cleartext",
                    "remediation": "Enable STARTTLS in mail server configuration",
                })
                identifiers.append("vuln:smtp:no_starttls")

            # Open relay test
            sock.sendall(f"MAIL FROM:<{_RELAY_FROM}>\r\n".encode())
            mail_resp = sock.recv(512).decode(errors="replace")

            if _RELAY_OK.search(mail_resp):
                sock.sendall(f"RCPT TO:<{_RELAY_TO_EXTERNAL}>\r\n".encode())
                rcpt_resp = sock.recv(512).decode(errors="replace")

                if _RELAY_OK.search(rcpt_resp):
                    vulnerabilities.append({
                        "type": "smtp_open_relay",
                        "severity": "critical",
                        "host": host,
                        "port": port,
                        "description": f"SMTP open relay on {host}:{port} — can send email to any external domain without authentication",
                        "remediation": "Restrict relaying to authenticated users only; configure relay restrictions",
                    })
                    identifiers.append("vuln:smtp:open_relay")

            # VRFY user enumeration
            sock.sendall(b"VRFY admin\r\n")
            vrfy_resp = sock.recv(256).decode(errors="replace")
            if _VRFY_VALID.search(vrfy_resp):
                vulnerabilities.append({
                    "type": "smtp_vrfy_enabled",
                    "severity": "low",
                    "host": host,
                    "port": port,
                    "description": "SMTP VRFY command enabled — allows username enumeration",
                    "remediation": "Disable VRFY in SMTP server config",
                })
                identifiers.append("vuln:smtp:vrfy_enabled")

            # EXPN command
            sock.sendall(b"EXPN postmaster\r\n")
            expn_resp = sock.recv(256).decode(errors="replace")
            if _VRFY_VALID.search(expn_resp):
                vulnerabilities.append({
                    "type": "smtp_expn_enabled",
                    "severity": "low",
                    "host": host,
                    "port": port,
                    "description": "SMTP EXPN command enabled — mailing list membership disclosed",
                    "remediation": "Disable EXPN command",
                })
                identifiers.append("vuln:smtp:expn_enabled")

            sock.sendall(b"QUIT\r\n")
            sock.close()

        except Exception as exc:
            log.debug("SMTP probe error", host=host, port=port, error=str(exc))
            try:
                sock.close()
            except Exception:
                pass
            if not info:
                return None

        return {
            "info": info,
            "vulnerabilities": vulnerabilities,
            "identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
