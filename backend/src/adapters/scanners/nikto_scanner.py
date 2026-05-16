"""Nikto web server scanner — checks for dangerous files, outdated software, and misconfigurations.

Nikto is a classic Kali Linux web vulnerability scanner that probes for 6700+ dangerous
files/CGIs, outdated server software, and version-specific problems.

Two-mode operation:
1. **Nikto binary** — if ``nikto`` is on PATH, invoked with JSON output
2. **Manual fallback** — extended HTTP checks covering Nikto's most critical checks
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import os
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Dangerous paths that Nikto checks — subset of the most critical findings
_NIKTO_PATHS: list[tuple[str, str, str]] = [
    # (path, finding_name, severity)
    ("/cgi-bin/test-cgi", "cgi_test_exposed", "high"),
    ("/cgi-bin/printenv", "cgi_printenv_exposed", "high"),
    ("/server-status", "apache_server_status", "medium"),
    ("/server-info", "apache_server_info", "medium"),
    ("/_profiler/phpinfo", "symfony_profiler_exposed", "critical"),
    ("/wp-config.php.bak", "wordpress_config_backup", "critical"),
    ("/config.php.bak", "config_backup_exposed", "critical"),
    ("/database.sql", "database_dump_exposed", "critical"),
    ("/dump.sql", "database_dump_exposed", "critical"),
    ("/backup.sql", "database_dump_exposed", "critical"),
    ("/web.config", "webconfig_exposed", "high"),
    ("/.htpasswd", "htpasswd_exposed", "critical"),
    ("/.htaccess", "htaccess_exposed", "medium"),
    ("/phpMyAdmin/", "phpmyadmin_exposed", "high"),
    ("/phpmyadmin/", "phpmyadmin_exposed", "high"),
    ("/pma/", "phpmyadmin_exposed", "high"),
    ("/adminer.php", "adminer_exposed", "high"),
    ("/test.php", "test_php_exposed", "medium"),
    ("/info.php", "phpinfo_exposed", "medium"),
    ("/php.php", "phpinfo_exposed", "medium"),
    ("/test/", "test_dir_exposed", "low"),
    ("/temp/", "temp_dir_exposed", "low"),
    ("/tmp/", "tmp_dir_exposed", "low"),
    ("/.svn/entries", "svn_entries_exposed", "high"),
    ("/.svn/wc.db", "svn_wcdb_exposed", "high"),
    ("/WEB-INF/web.xml", "webinf_exposed", "high"),
    ("/WEB-INF/classes/", "webinf_classes_exposed", "high"),
    ("/spring/", "spring_actuator_exposed", "medium"),
    ("/actuator", "spring_actuator_exposed", "medium"),
    ("/actuator/env", "spring_actuator_env_exposed", "critical"),
    ("/actuator/heapdump", "spring_heapdump_exposed", "critical"),
    ("/api/swagger.json", "swagger_exposed", "low"),
    ("/swagger-ui.html", "swagger_exposed", "low"),
    ("/swagger/index.html", "swagger_exposed", "low"),
    ("/api-docs", "swagger_exposed", "low"),
    ("/v1/api-docs", "swagger_exposed", "low"),
    ("/console", "web_console_exposed", "high"),
    ("/jmx-console/", "jmx_console_exposed", "critical"),
    ("/web-console/", "web_console_exposed", "high"),
]

# Server version disclosure via response headers
_VERSION_HEADERS = ["Server", "X-Powered-By", "X-AspNet-Version", "X-Runtime", "X-Generator"]


class NiktoScanner(BaseOsintScanner):
    """Web server vulnerability scanner — Nikto-style checks.

    Probes for dangerous files, exposed admin panels, server version disclosure,
    outdated software indicators, and common web misconfigurations.
    """

    scanner_name = "nikto"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("nikto"):
            return await self._run_nikto_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_nikto_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"nikto_{run_id}.json")
        cmd = [
            "nikto",
            "-h", base_url,
            "-Format", "json",
            "-output", out_file,
            "-nointeractive",
            "-Tuning", "123457890abc",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("Nikto subprocess timed out", target=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        vulnerabilities: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                for vuln in data.get("vulnerabilities", []):
                    vulnerabilities.append({
                        "id": vuln.get("id", ""),
                        "method": vuln.get("method", "GET"),
                        "url": vuln.get("url", ""),
                        "msg": vuln.get("msg", ""),
                        "references": vuln.get("references", ""),
                    })
            except Exception as exc:
                log.warning("Failed to parse Nikto output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        return {
            "input": input_value,
            "scan_mode": "nikto_binary",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_findings": len(vulnerabilities),
            "extracted_identifiers": [f"url:{v['url']}" for v in vulnerabilities if v.get("url")],
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        server_info: dict[str, str] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"},
        ) as client:
            # 1. Baseline request — collect server version headers
            try:
                resp = await client.get(base_url)
                for hdr in _VERSION_HEADERS:
                    val = resp.headers.get(hdr, "")
                    if val:
                        server_info[hdr] = val
                        findings.append({
                            "id": "version_disclosure",
                            "severity": "info",
                            "description": f"Server version disclosed via {hdr}: {val}",
                            "url": base_url,
                        })

                # Check for HTTP methods
                allowed = resp.headers.get("Allow", "")
                if any(m in allowed for m in ("PUT", "DELETE", "TRACE", "CONNECT")):
                    findings.append({
                        "id": "dangerous_http_methods",
                        "severity": "medium",
                        "description": f"Dangerous HTTP methods enabled: {allowed}",
                        "url": base_url,
                    })
            except Exception as exc:
                log.debug("Nikto baseline request failed", url=base_url, error=str(exc))

            # 2. TRACE method check (XST attack vector)
            try:
                resp = await client.request("TRACE", base_url)
                if resp.status_code == 200:
                    findings.append({
                        "id": "http_trace_enabled",
                        "severity": "medium",
                        "description": "HTTP TRACE method enabled (Cross-Site Tracing risk)",
                        "url": base_url,
                    })
                    identifiers.append(f"vuln:http_trace:{_extract_hostname(base_url)}")
            except Exception:
                pass

            # 3. Sensitive path enumeration
            for path, finding_id, severity in _NIKTO_PATHS:
                target = base_url.rstrip("/") + path
                try:
                    resp = await client.get(target)
                    if resp.status_code in (200, 301, 302, 403):
                        findings.append({
                            "id": finding_id,
                            "severity": severity,
                            "description": f"{finding_id.replace('_', ' ').title()} at {path}",
                            "url": target,
                            "status_code": resp.status_code,
                        })
                        ident = f"url:{target}"
                        if ident not in identifiers:
                            identifiers.append(ident)
                except Exception:
                    pass

        # Severity summary
        severity_counts = {}
        for f in findings:
            s = f.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "server_info": server_info,
            "findings": findings,
            "total_findings": len(findings),
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


def _extract_hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""
