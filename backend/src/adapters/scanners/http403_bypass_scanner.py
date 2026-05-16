"""HTTP 403 Bypass — forbidden access bypass vulnerability scanner.

Attempts to bypass 403 Forbidden responses using path traversal mutations,
URL encoding, case normalization, HTTP method override, header injection,
and path prefix tricks. Common against misconfigured WAFs and middleware.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Paths commonly protected by 403
_PROTECTED_PATHS: list[str] = [
    "/admin", "/admin/", "/admin/login", "/admin/dashboard",
    "/.env", "/.git", "/.git/HEAD", "/.htaccess", "/.htpasswd",
    "/api/admin", "/api/v1/admin", "/api/internal",
    "/config", "/config.php", "/wp-admin", "/wp-admin/",
    "/manager", "/console", "/actuator", "/actuator/env",
    "/server-status", "/server-info", "/phpinfo.php",
    "/backup", "/backup.sql", "/database.sql",
]

# Path mutation techniques
def _generate_path_mutations(path: str) -> list[tuple[str, str]]:
    mutations: list[tuple[str, str]] = []
    base = path.rstrip("/")
    name = base.lstrip("/")

    # Direct path tricks
    mutations += [
        (f"{base}//", "double_slash"),
        (f"{base}/.", "dot_suffix"),
        (f"{base}/..", "dotdot_suffix"),
        (f"{base}%20", "space_encoded"),
        (f"{base}%09", "tab_encoded"),
        (f"/{name.upper()}", "uppercase"),
        (f"/{name.lower()}", "lowercase"),
        (f"/{name[:len(name)//2].upper()}{name[len(name)//2:]}", "mixed_case"),
        (f"/..{base}", "prefix_dotdot"),
        (f"/{name};/", "semicolon_suffix"),
        (f"/{name}#", "fragment"),
        (f"/{name}?", "query_trick"),
        (f"/{name}.json", "json_ext"),
        (f"/{name}.html", "html_ext"),
        (f"/{name}%2F", "encoded_slash"),
        (f"/{name}%252F", "double_encoded_slash"),
        (f"/./{'/' + name}", "dot_prefix"),
    ]

    # URL path traversal prefix tricks
    for prefix in ["/a/..%2F", "/%2F/", "/..;/"]:
        mutations.append((f"{prefix}{name}", f"prefix_{prefix[:5].strip('/')}"))

    return mutations


# Header injection bypass techniques
_BYPASS_HEADERS: list[dict[str, str]] = [
    {"X-Original-URL": ""},          # Will be filled per path
    {"X-Rewrite-URL": ""},
    {"X-Custom-IP-Authorization": "127.0.0.1"},
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Forwarded-For": "localhost"},
    {"X-Remote-IP": "127.0.0.1"},
    {"X-Client-IP": "127.0.0.1"},
    {"X-Host": "localhost"},
    {"X-Originating-IP": "127.0.0.1"},
    {"X-Remote-Addr": "127.0.0.1"},
    {"X-True-IP": "127.0.0.1"},
    {"X-ProxyUser-Ip": "127.0.0.1"},
]

# HTTP method override
_METHOD_OVERRIDES: list[tuple[str, str]] = [
    ("X-HTTP-Method-Override", "GET"),
    ("X-HTTP-Method", "GET"),
    ("X-Method-Override", "GET"),
]


class Http403BypassScanner(BaseOsintScanner):
    """HTTP 403 Forbidden bypass vulnerability scanner.

    Identifies protected endpoints returning 403, then attempts bypasses via:
    path mutations, header injection (X-Forwarded-For, X-Original-URL),
    method override, URL encoding tricks, and case normalization.
    """

    scanner_name = "http403_bypass"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        forbidden_paths: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; 403BypassScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            # Step 1: Find 403-returning paths
            async def check_forbidden(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 403:
                            forbidden_paths.append(path)
                    except Exception:
                        pass

            await asyncio.gather(*[check_forbidden(p) for p in _PROTECTED_PATHS])

            # Step 2: Attempt bypasses on each 403 path
            async def try_path_mutation(path: str, mutated: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + mutated
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 201, 301, 302):
                            vulnerabilities.append({
                                "type": "403_bypass_path",
                                "severity": "high",
                                "original_path": path,
                                "bypass_path": mutated,
                                "technique": technique,
                                "status_code": resp.status_code,
                                "description": f"403 bypassed via path mutation ({technique})",
                                "remediation": "Normalize URL paths before access control checks",
                            })
                            ident = f"vuln:403bypass:path:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            async def try_header_bypass(path: str, headers: dict[str, str], technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    actual_headers = {}
                    for k, v in headers.items():
                        actual_headers[k] = v if v else path
                    try:
                        resp = await client.get(url, headers=actual_headers)
                        if resp.status_code in (200, 201):
                            vulnerabilities.append({
                                "type": "403_bypass_header",
                                "severity": "high",
                                "original_path": path,
                                "headers_used": actual_headers,
                                "technique": technique,
                                "status_code": resp.status_code,
                                "description": f"403 bypassed via header injection ({technique})",
                                "remediation": "Validate access control at application layer, not via proxy headers",
                            })
                            ident = f"vuln:403bypass:header:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for path in forbidden_paths[:6]:
                # Path mutations
                for mutated, technique in _generate_path_mutations(path)[:12]:
                    tasks.append(try_path_mutation(path, mutated, technique))

                # Header bypasses
                for header_dict in _BYPASS_HEADERS:
                    technique = list(header_dict.keys())[0].lower().replace("-", "_")
                    tasks.append(try_header_bypass(path, header_dict, technique))

                # Method override POST → GET
                for override_header, override_value in _METHOD_OVERRIDES:
                    tasks.append(try_header_bypass(
                        path,
                        {override_header: override_value},
                        f"method_override_{override_header.lower()}",
                    ))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "forbidden_paths_found": forbidden_paths,
            "bypasses_found": len(vulnerabilities),
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
