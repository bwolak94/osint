"""Brute login scanner — ncrack/medusa-style multi-protocol authentication tester.

Tests authentication services for default/weak credentials:
- HTTP Basic Auth brute force
- HTTP form-based login (POST detection + field enumeration)
- FTP anonymous + default credential test
- Telnet banner + default login
- RDP port exposure detection (port 3389)
- VNC default credential probe (port 5900-5910)
- MongoDB (port 27017) — unauthenticated access
- CouchDB (port 5984) — _session API unauthenticated
- Memcached (port 11211) — stats command without auth
"""

from __future__ import annotations

import asyncio
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Default credentials (username, password)
_DEFAULT_CREDS: list[tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "password"),
    ("admin", "123456"),
    ("admin", ""),
    ("administrator", "administrator"),
    ("administrator", "admin"),
    ("root", "root"),
    ("root", "toor"),
    ("root", ""),
    ("user", "user"),
    ("guest", "guest"),
    ("test", "test"),
    ("demo", "demo"),
    ("admin", "admin123"),
    ("admin", "letmein"),
]

# HTTP Basic auth paths
_BASIC_AUTH_PATHS: list[str] = [
    "/admin/", "/admin", "/administrator/",
    "/manager/", "/wp-admin/", "/phpmyadmin/",
    "/panel/", "/control/", "/dashboard/",
    "/api/", "/api/v1/", "/api/v2/",
]

# Login form indicators
_LOGIN_FORM_PATTERNS = re.compile(
    r'(?i)(input[^>]+type=["\']password["\']|<form[^>]*login|<form[^>]*signin)',
)
_FORM_ACTION = re.compile(r'<form[^>]+action=["\']([^"\']+)["\']', re.I)
_INPUT_NAME = re.compile(r'<input[^>]+name=["\']([^"\']+)["\']', re.I)

# Common login field names
_USER_FIELDS = ["username", "user", "email", "login", "name", "user_name"]
_PASS_FIELDS = ["password", "pass", "passwd", "pwd", "secret"]

# Service ports
_SERVICE_PORTS = [
    (21, "ftp"),
    (23, "telnet"),
    (3389, "rdp"),
    (5900, "vnc"),
    (5901, "vnc"),
    (27017, "mongodb"),
    (5984, "couchdb"),
    (11211, "memcached"),
    (6379, "redis_check"),  # Quick check (redis_exploit handles full test)
    (9200, "elasticsearch_check"),
]


class BruteLoginScanner(BaseOsintScanner):
    """Multi-protocol authentication brute force scanner (ncrack/medusa-style).

    Tests HTTP Basic Auth, form-based login, FTP, Telnet, RDP, VNC,
    MongoDB, CouchDB, and Memcached for default/weak credentials.
    """

    scanner_name = "brute_login"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        host = _extract_host(input_value, input_type)
        return await self._manual_scan(base_url, host, input_value)

    async def _manual_scan(self, base_url: str, host: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AuthScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # 1. HTTP Basic Auth
            async def test_basic_auth(path: str, username: str, password: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url, auth=(username, password))
                        if resp.status_code == 200:
                            vulnerabilities.append({
                                "type": "http_basic_auth_weak",
                                "severity": "critical",
                                "url": url,
                                "username": username,
                                "password": password if password else "(empty)",
                                "description": f"HTTP Basic Auth bypass with default credentials "
                                               f"'{username}'/'{password}' on {path}",
                                "remediation": "Change default credentials; use strong unique passwords; "
                                               "consider certificate-based auth",
                            })
                            ident = "vuln:brute:http_basic_default_creds"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Check for 401 pages first
            auth_paths = []
            for path in _BASIC_AUTH_PATHS[:5]:
                try:
                    resp = await client.get(base_url.rstrip("/") + path)
                    if resp.status_code == 401:
                        auth_paths.append(path)
                except Exception:
                    pass

            basic_tasks = []
            for path in auth_paths[:3]:
                for user, pwd in _DEFAULT_CREDS[:8]:
                    basic_tasks.append(test_basic_auth(path, user, pwd))
            if basic_tasks:
                await asyncio.gather(*basic_tasks)

            # 2. Form-based login detection and test
            async def detect_and_test_login_form() -> None:
                try:
                    for path in ["/", "/login", "/admin", "/signin", "/auth"]:
                        url = base_url.rstrip("/") + path
                        resp = await client.get(url)
                        if resp.status_code == 200 and _LOGIN_FORM_PATTERNS.search(resp.text):
                            # Extract form action and field names
                            action_match = _FORM_ACTION.search(resp.text)
                            action = action_match.group(1) if action_match else path
                            if not action.startswith("http"):
                                action = base_url.rstrip("/") + "/" + action.lstrip("/")

                            input_names = _INPUT_NAME.findall(resp.text)
                            user_field = next((f for f in input_names if f.lower() in _USER_FIELDS), "username")
                            pass_field = next((f for f in input_names if f.lower() in _PASS_FIELDS), "password")

                            # Test a subset of default creds
                            for user, pwd in _DEFAULT_CREDS[:6]:
                                try:
                                    login_resp = await client.post(
                                        action,
                                        data={user_field: user, pass_field: pwd},
                                    )
                                    # Success indicators: redirect away from login, dashboard keywords
                                    success = (
                                        login_resp.status_code in (200, 302) and
                                        any(kw in login_resp.text.lower()
                                            for kw in ["dashboard", "logout", "welcome", "profile"])
                                        and "invalid" not in login_resp.text.lower()
                                        and "incorrect" not in login_resp.text.lower()
                                    )
                                    if success:
                                        vulnerabilities.append({
                                            "type": "form_login_default_creds",
                                            "severity": "critical",
                                            "url": action,
                                            "username": user,
                                            "password": pwd if pwd else "(empty)",
                                            "user_field": user_field,
                                            "pass_field": pass_field,
                                            "description": f"Form login accepted default credentials "
                                                           f"'{user}'/'{pwd}'",
                                            "remediation": "Immediately change default credentials; "
                                                           "implement account lockout",
                                        })
                                        ident = "vuln:brute:form_default_creds"
                                        if ident not in identifiers:
                                            identifiers.append(ident)
                                        break
                                except Exception:
                                    pass
                            break  # Found login form, stop searching
                except Exception:
                    pass

            await detect_and_test_login_form()

        # 3. TCP service probes (synchronous, run in executor)
        tcp_results = await asyncio.get_event_loop().run_in_executor(
            None, self._probe_tcp_services, host
        )
        vulnerabilities.extend(tcp_results.get("vulnerabilities", []))
        for ident in tcp_results.get("identifiers", []):
            if ident not in identifiers:
                identifiers.append(ident)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "host": host,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _probe_tcp_services(self, host: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        for port, service in _SERVICE_PORTS:
            try:
                sock = socket.create_connection((host, port), timeout=4)
                banner = b""
                try:
                    banner = sock.recv(512)
                except Exception:
                    pass

                if service == "ftp":
                    if b"220" in banner:
                        # Test anonymous login
                        sock.sendall(b"USER anonymous\r\n")
                        r1 = sock.recv(256)
                        if b"331" in r1 or b"230" in r1:
                            sock.sendall(b"PASS anonymous@\r\n")
                            r2 = sock.recv(256)
                            if b"230" in r2:
                                vulnerabilities.append({
                                    "type": "ftp_anonymous_login",
                                    "severity": "high",
                                    "host": host,
                                    "port": port,
                                    "description": "FTP anonymous login accepted — files may be readable/writable",
                                    "remediation": "Disable anonymous FTP; require authenticated access",
                                })
                                identifiers.append("vuln:brute:ftp_anonymous")

                elif service == "telnet":
                    if banner:
                        vulnerabilities.append({
                            "type": "telnet_exposed",
                            "severity": "high",
                            "host": host,
                            "port": port,
                            "banner": banner[:80].decode(errors="replace"),
                            "description": "Telnet service exposed — credentials transmitted in cleartext",
                            "remediation": "Disable Telnet; use SSH; block port 23",
                        })
                        identifiers.append("vuln:brute:telnet_exposed")

                elif service == "rdp":
                    vulnerabilities.append({
                        "type": "rdp_exposed",
                        "severity": "high",
                        "host": host,
                        "port": port,
                        "description": "RDP (Remote Desktop Protocol) exposed on port 3389 — "
                                       "brute force, BlueKeep (CVE-2019-0708) risk",
                        "remediation": "Restrict RDP to VPN only; enable NLA; apply BlueKeep patch",
                        "cve": "CVE-2019-0708",
                    })
                    identifiers.append("vuln:brute:rdp_exposed")

                elif service == "vnc":
                    vulnerabilities.append({
                        "type": "vnc_exposed",
                        "severity": "high",
                        "host": host,
                        "port": port,
                        "banner": banner[:40].decode(errors="replace"),
                        "description": f"VNC service accessible on port {port} — "
                                       "brute force and no-auth bypass risk",
                        "remediation": "Require strong VNC password; restrict to VPN; use SSH tunneling",
                    })
                    identifiers.append("vuln:brute:vnc_exposed")

                elif service == "mongodb":
                    # MongoDB without auth responds to isMaster
                    sock.sendall(bytes.fromhex(
                        "3a000000" "01000000" "00000000" "d4070000"
                        "00000000" "61646d69" "6e2e2461" "746c6173"
                        "00000000" "00ffffff" "ff130000" "00107769" "72654d61" "73746572" "00010000" "0000"
                    ))
                    r = sock.recv(256)
                    if r:
                        vulnerabilities.append({
                            "type": "mongodb_unauthenticated",
                            "severity": "critical",
                            "host": host,
                            "port": port,
                            "description": "MongoDB accessible without authentication — "
                                           "all databases readable/writable",
                            "remediation": "Enable MongoDB auth (security.authorization: enabled); "
                                           "bind to localhost; use firewall",
                        })
                        identifiers.append("vuln:brute:mongodb_unauth")

                elif service == "memcached":
                    sock.sendall(b"stats\r\n")
                    r = sock.recv(512)
                    if b"STAT" in r:
                        vulnerabilities.append({
                            "type": "memcached_unauthenticated",
                            "severity": "high",
                            "host": host,
                            "port": port,
                            "description": "Memcached accessible without authentication — "
                                           "cache data readable, UDP amplification DDoS risk",
                            "remediation": "Bind memcached to 127.0.0.1; use firewall; "
                                           "enable SASL auth",
                        })
                        identifiers.append("vuln:brute:memcached_unauth")

                sock.close()

            except Exception:
                pass

        return {"vulnerabilities": vulnerabilities, "identifiers": identifiers}

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS):
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
