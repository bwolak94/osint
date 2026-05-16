"""Web shell scanner — detects uploaded/backdoored web shells on target servers.

Known web shell signatures detected:
- c99shell, r57shell, b374k, WSO (Web Shell by oRb), China Chopper
- p0wny-shell, weevely, laudanum, tennc, PhpSpy
- Common shell upload paths and filenames
- Shell behavioral indicators: eval+base64, system/exec in query params
- Anomalous PHP/ASP/JSP files in upload directories
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Known web shell filenames and paths
_SHELL_PATHS: list[tuple[str, str]] = [
    # Generic shells
    ("/shell.php", "generic"),
    ("/cmd.php", "generic"),
    ("/c99.php", "c99"),
    ("/r57.php", "r57"),
    ("/b374k.php", "b374k"),
    ("/wso.php", "wso"),
    ("/php-backdoor.php", "generic"),
    ("/backdoor.php", "generic"),
    ("/webshell.php", "generic"),
    ("/terminal.php", "generic"),
    ("/exec.php", "generic"),
    ("/system.php", "generic"),
    ("/upload/shell.php", "generic"),
    ("/uploads/shell.php", "generic"),
    ("/images/shell.php", "generic"),
    ("/tmp/shell.php", "generic"),
    ("/files/shell.php", "generic"),
    ("/media/shell.php", "generic"),
    # JSP shells
    ("/shell.jsp", "jsp"),
    ("/cmd.jsp", "jsp"),
    ("/payload.jsp", "jsp"),
    # ASP/ASPX shells
    ("/shell.asp", "asp"),
    ("/shell.aspx", "aspx"),
    ("/cmd.asp", "asp"),
    ("/cmd.aspx", "aspx"),
    # Common obfuscated names
    ("/wp-content/uploads/shell.php", "wordpress"),
    ("/wp-content/uploads/image.php", "wordpress"),
    ("/wp-includes/shell.php", "wordpress"),
    ("/administrator/shell.php", "joomla"),
    ("/sites/default/files/shell.php", "drupal"),
    # China Chopper indicator paths
    ("/index.php?chopper", "china_chopper"),
    ("/404.php", "404_shell"),
    ("/1.php", "numbered"),
    ("/2.php", "numbered"),
    ("/test.php", "test"),
    ("/info.php", "phpinfo"),
    ("/config.php", "config_leak"),
    ("/db.php", "db_leak"),
    ("/include/shell.php", "include"),
    ("/lib/shell.php", "lib"),
]

# Web shell content signatures in responses
_SHELL_SIGNATURES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r'(?i)c99shell|c99 shell|c99\.php', re.I), "c99shell", "critical"),
    (re.compile(r'(?i)r57shell|r57 shell', re.I), "r57shell", "critical"),
    (re.compile(r'b374k|B374K Shell', re.I), "b374k", "critical"),
    (re.compile(r'(?i)wso 2\.|WSO Shell', re.I), "wso_shell", "critical"),
    (re.compile(r'China Chopper|<title>404</title>.*eval\(|chopper', re.I), "china_chopper", "critical"),
    (re.compile(r'p0wny.shell|p0wny@shell', re.I), "p0wny", "critical"),
    (re.compile(r'PhpSpy|phpspy', re.I), "phpspy", "critical"),
    (re.compile(r'eval\s*\(\s*(?:base64_decode|gzinflate|str_rot13|gzuncompress)\s*\(', re.I),
     "obfuscated_eval", "critical"),
    (re.compile(r'assert\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)', re.I), "assert_injection", "critical"),
    (re.compile(r'\$_(?:GET|POST|REQUEST)\[[\'"]cmd[\'"]\]', re.I), "cmd_param_shell", "critical"),
    (re.compile(r'system\s*\(\s*\$_(?:GET|POST|REQUEST)', re.I), "system_shell", "critical"),
    (re.compile(r'exec\s*\(\s*\$_(?:GET|POST|REQUEST)', re.I), "exec_shell", "critical"),
    (re.compile(r'passthru\s*\(\s*\$_(?:GET|POST)', re.I), "passthru_shell", "critical"),
    (re.compile(r'preg_replace\s*\(.*\/e[,\']', re.I), "preg_replace_e_shell", "high"),
    (re.compile(r'FilesMan|FilesMan Shell', re.I), "filesmen", "critical"),
    (re.compile(r'laudanum|Laudanum', re.I), "laudanum", "high"),
]

# phpinfo() exposure (separate from shells but related)
_PHPINFO_PATTERN = re.compile(r'PHP Version|phpinfo\(\)|php_info', re.I)

# Suspicious upload directory scan
_UPLOAD_DIRS: list[str] = [
    "/uploads/", "/upload/", "/files/", "/media/",
    "/images/", "/img/", "/assets/", "/static/",
    "/wp-content/uploads/", "/data/",
]

# Suspicious PHP file pattern in directory listings
_PHP_IN_UPLOAD = re.compile(r'href="([^"]*\.php)"', re.I)


class WebShellScanner(BaseOsintScanner):
    """Web shell detection scanner.

    Probes common shell paths, detects shell signatures in responses,
    finds phpinfo() exposures, and scans upload directories for suspicious PHP files.
    """

    scanner_name = "webshell"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WebShellScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            async def probe_shell_path(path: str, shell_type: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code != 200 or len(resp.content) < 10:
                            return

                        body = resp.text

                        # Check phpinfo
                        if _PHPINFO_PATTERN.search(body) and "php" in path.lower():
                            vulnerabilities.append({
                                "type": "phpinfo_exposed",
                                "severity": "medium",
                                "url": url,
                                "description": "phpinfo() exposed — reveals PHP config, loaded modules, env vars",
                                "remediation": "Remove phpinfo() files from production; restrict access",
                            })
                            if "info:webshell:phpinfo" not in identifiers:
                                identifiers.append("info:webshell:phpinfo")
                            return

                        # Check known shell signatures
                        for pattern, sig_name, severity in _SHELL_SIGNATURES:
                            if pattern.search(body):
                                vulnerabilities.append({
                                    "type": "webshell_detected",
                                    "severity": severity,
                                    "url": url,
                                    "shell_type": sig_name,
                                    "shell_family": shell_type,
                                    "evidence": f"Signature: {sig_name}",
                                    "description": f"Web shell ({sig_name}) detected at {path}",
                                    "remediation": "Remove shell immediately; scan all files for malware; "
                                                   "review access logs; rotate credentials",
                                })
                                ident = f"vuln:webshell:{sig_name}"
                                if ident not in identifiers:
                                    identifiers.append("vuln:webshell:detected")
                                return

                        # Check if PHP file in non-PHP path returns PHP-looking content
                        if path.endswith(".php") and "<?php" in body[:500]:
                            vulnerabilities.append({
                                "type": "suspicious_php_file",
                                "severity": "high",
                                "url": url,
                                "description": f"Suspicious PHP file accessible at {path} — "
                                               "may be an uploaded shell or backdoor",
                                "remediation": "Investigate file origin; remove if unauthorized",
                            })
                            if "vuln:webshell:suspicious_php" not in identifiers:
                                identifiers.append("vuln:webshell:suspicious_php")

                    except Exception:
                        pass

            async def scan_upload_directory(dir_path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + dir_path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and "Index of" in resp.text:
                            # Directory listing enabled — look for PHP files
                            php_files = _PHP_IN_UPLOAD.findall(resp.text)
                            if php_files:
                                vulnerabilities.append({
                                    "type": "php_in_upload_dir",
                                    "severity": "critical",
                                    "url": url,
                                    "php_files": php_files[:10],
                                    "description": f"PHP files found in upload directory {dir_path} — "
                                                   f"possible web shell upload: {', '.join(php_files[:3])}",
                                    "remediation": "Disable PHP execution in upload directories; "
                                                   "remove PHP files; disable directory listing",
                                })
                                if "vuln:webshell:php_in_uploads" not in identifiers:
                                    identifiers.append("vuln:webshell:php_in_uploads")
                    except Exception:
                        pass

            tasks = []
            for path, shell_type in _SHELL_PATHS:
                tasks.append(probe_shell_path(path, shell_type))
            for dir_path in _UPLOAD_DIRS:
                tasks.append(scan_upload_directory(dir_path))

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
