"""Wfuzz-style web application fuzzer — parameter and path discovery scanner.

Complements ffuf/feroxbuster with parameter-focused fuzzing:
- Hidden GET/POST parameter discovery (content-length variance analysis)
- Virtual host fuzzing via Host header mutation
- Cookie value fuzzing for session fixation / parameter injection
- Response differentiation: 200 vs 302 vs 500 anomalies
- Backup/swap file discovery (.bak, .old, ~, .swp, .orig, .save)
- Technology-specific parameter names (debug, trace, test, verbose, env)
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

# Parameter wordlist — technology-specific debug/hidden params
_DEBUG_PARAMS: list[str] = [
    "debug", "test", "trace", "verbose", "env", "environment",
    "admin", "administrator", "dev", "development", "staging",
    "preview", "internal", "secret", "hidden", "bypass",
    "callback", "redirect", "next", "return", "goto",
    "jsonp", "format", "output", "template", "view",
    "cmd", "exec", "command", "run", "shell",
    "file", "path", "include", "require", "load",
    "url", "uri", "src", "source", "dest", "destination",
    "page", "action", "method", "type", "mode",
    "show", "display", "lang", "language", "locale",
    "token", "key", "api_key", "apikey", "access_token",
    "XDEBUG_SESSION_START", "XDEBUG_PROFILE", "XDEBUG_TRACE",
    "phpinfo", "phpmyadmin", "_profiler", "__debug__",
]

# Backup / swap file extensions
_BACKUP_EXTENSIONS: list[str] = [
    ".bak", ".old", ".orig", ".save", ".backup",
    ".~", ".swp", ".tmp", ".copy", ".disabled",
    ".1", ".2", ".bkp", ".bk", "~",
    ".tar.gz", ".zip", ".tar", ".gz",
    "_backup", "_old", "-backup", "-old",
]

# Common files to check for backup variants
_COMMON_FILES: list[str] = [
    "index", "config", "configuration", "settings", "database",
    "db", "admin", "login", "auth", "user", "users",
    "wp-config", "local", "production", "staging",
    ".htaccess", ".env", "web.config",
]

# Virtual host prefixes for vhost fuzzing
_VHOST_PREFIXES: list[str] = [
    "admin", "dev", "staging", "test", "internal", "api",
    "mail", "smtp", "ftp", "vpn", "remote", "portal",
    "backend", "dashboard", "monitor", "status", "beta",
]

# Response size variance threshold for parameter discovery
_SIZE_VARIANCE_THRESHOLD = 50  # bytes


class WFuzzScanner(BaseOsintScanner):
    """Wfuzz-style parameter and path fuzzer.

    Discovers hidden GET/POST parameters via response variance analysis,
    backup files, virtual hosts, and debug parameter injection.
    """

    scanner_name = "wfuzz"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        findings: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WFuzzScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            # Baseline response
            baseline_size = 0
            baseline_status = 0
            try:
                resp = await client.get(base_url)
                baseline_size = len(resp.content)
                baseline_status = resp.status_code
            except Exception:
                pass

            # 1. Hidden parameter discovery via GET injection
            async def fuzz_param(param: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + f"/?{param}=FUZZ_VALUE_123"
                    try:
                        resp = await client.get(url)
                        size_diff = abs(len(resp.content) - baseline_size)

                        # Significant response change = parameter accepted
                        if (resp.status_code != baseline_status or
                                size_diff > _SIZE_VARIANCE_THRESHOLD * 2):
                            evidence = ""
                            if "FUZZ_VALUE_123" in resp.text:
                                evidence = "value reflected in response"
                            elif resp.status_code == 500:
                                evidence = "server error triggered"
                            elif resp.status_code != baseline_status:
                                evidence = f"status changed {baseline_status}→{resp.status_code}"
                            else:
                                evidence = f"response size changed by {size_diff} bytes"

                            severity = "high" if param in ("cmd", "exec", "command", "shell", "run",
                                                            "file", "include", "require") else "medium"
                            findings.append({
                                "type": "hidden_parameter",
                                "severity": severity,
                                "url": url,
                                "parameter": param,
                                "evidence": evidence,
                                "description": f"Hidden GET parameter '{param}' causes response variance",
                                "remediation": "Audit accepted parameters; remove debug/test params from production",
                            })
                            ident = f"info:wfuzz:param:{param}"
                            if ident not in identifiers:
                                identifiers.append("info:wfuzz:hidden_params")
                    except Exception:
                        pass

            # 2. Backup file discovery
            async def fuzz_backup(filename: str, ext: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + f"/{filename}{ext}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and len(resp.content) > 10:
                            content_type = resp.headers.get("content-type", "")
                            # Avoid flagging HTML error pages as backup files
                            if "html" not in content_type.lower() or len(resp.content) > 500:
                                sev = "critical" if any(
                                    kw in resp.text.lower()
                                    for kw in ["password", "secret", "database", "db_pass"]
                                ) else "high"
                                vulnerabilities.append({
                                    "type": "backup_file_exposed",
                                    "severity": sev,
                                    "url": url,
                                    "filename": f"{filename}{ext}",
                                    "size": len(resp.content),
                                    "description": f"Backup/swap file accessible: {filename}{ext}",
                                    "remediation": "Remove backup files from web root; add rules to deny .bak/.old access",
                                })
                                ident = "vuln:wfuzz:backup_files"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

            # 3. Virtual host fuzzing
            async def fuzz_vhost(prefix: str) -> None:
                async with semaphore:
                    # Extract domain from base_url
                    import re as _re
                    domain_match = _re.search(r'https?://([^/:]+)', base_url)
                    if not domain_match:
                        return
                    domain = domain_match.group(1)
                    # Remove existing subdomain prefix if any
                    parts = domain.split(".")
                    if len(parts) > 2:
                        root_domain = ".".join(parts[-2:])
                    else:
                        root_domain = domain

                    vhost = f"{prefix}.{root_domain}"
                    try:
                        resp = await client.get(base_url, headers={"Host": vhost})
                        if resp.status_code == 200 and len(resp.content) > 100:
                            size_diff = abs(len(resp.content) - baseline_size)
                            if size_diff > _SIZE_VARIANCE_THRESHOLD:
                                findings.append({
                                    "type": "virtual_host_found",
                                    "severity": "medium",
                                    "url": base_url,
                                    "vhost": vhost,
                                    "description": f"Virtual host '{vhost}' returns different content — "
                                                   "potential internal application exposed",
                                    "remediation": "Ensure virtual host access controls are correct; "
                                                   "restrict internal vhosts",
                                })
                                if "info:wfuzz:vhosts" not in identifiers:
                                    identifiers.append("info:wfuzz:vhosts")
                    except Exception:
                        pass

            tasks = []
            # Fuzz debug params
            for param in _DEBUG_PARAMS[:30]:
                tasks.append(fuzz_param(param))
            # Fuzz backup files
            for filename in _COMMON_FILES[:8]:
                for ext in _BACKUP_EXTENSIONS[:8]:
                    tasks.append(fuzz_backup(filename, ext))
            # Fuzz vhosts
            for prefix in _VHOST_PREFIXES[:10]:
                tasks.append(fuzz_vhost(prefix))

            await asyncio.gather(*tasks)

        all_findings = vulnerabilities + findings
        severity_counts: dict[str, int] = {}
        for f in all_findings:
            s = f.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "findings": findings,
            "total_found": len(all_findings),
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
