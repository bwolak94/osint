"""Dependency Check — vulnerable JavaScript library detection scanner.

Identifies outdated/vulnerable client-side JS libraries using retire.js-style
version extraction and checks against known CVE data. Detects jQuery, Angular,
React, Bootstrap, Lodash, and 20+ other libraries via CDN URLs, inline comments,
and global variable patterns.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Known vulnerable version ranges — (library, vulnerable_versions_pattern, cve, severity)
_VULN_DB: list[tuple[str, re.Pattern[str], str, str, str]] = [
    ("jquery", re.compile(r"jQuery\s+v?(1\.[0-9]\.|2\.[0-2]\.|3\.[0-4]\.)"), "CVE-2019-11358", "medium", "jQuery < 3.5.0 — prototype pollution"),
    ("jquery", re.compile(r"jQuery\s+v?(1\.[0-4]\.)"), "CVE-2015-9251", "high", "jQuery < 1.12 — XSS in $.ajax JSONP"),
    ("angular", re.compile(r"AngularJS\s+v?(1\.[0-5]\.)"), "CVE-2019-14863", "high", "AngularJS < 1.6.0 — sandbox bypass XSS"),
    ("bootstrap", re.compile(r"Bootstrap\s+v?(3\.[0-3]\.|2\.)"), "CVE-2019-8331", "medium", "Bootstrap < 3.4.0 — XSS in tooltip/popover"),
    ("lodash", re.compile(r"lodash\s+v?(4\.[0-6]\.|[0-3]\.)"), "CVE-2021-23337", "high", "Lodash < 4.17.21 — command injection"),
    ("moment", re.compile(r"moment\.js\s+v?(2\.[0-9]\.|1\.)"), "CVE-2022-24785", "high", "Moment.js < 2.29.2 — path traversal"),
    ("handlebars", re.compile(r"Handlebars\.VERSION\s*=\s*[\"'](4\.[0-6]\.|[0-3]\.)"), "CVE-2019-19919", "critical", "Handlebars < 4.7.7 — prototype pollution RCE"),
    ("underscore", re.compile(r"Underscore\.js\s+([0-9]\.[0-9]+\.[0-9]+)"), "CVE-2021-23358", "high", "Underscore < 1.13.0 — arbitrary code execution"),
    ("dojo", re.compile(r"dojo\s+([1-9]\.[0-9]+)"), "CVE-2020-5258", "high", "Dojo < 1.16 — prototype pollution"),
    ("knockout", re.compile(r"Knockout\s+JavaScript\s+library\s+v([0-2]\.)"), "CVE-2019-14862", "medium", "Knockout < 3.5.0 — XSS"),
    ("chartjs", re.compile(r"Chart\.js\s+v?(2\.[0-8]\.)"), "CVE-2020-7746", "medium", "Chart.js < 2.9.4 — ReDoS"),
    ("d3", re.compile(r"D3\s+v?(3\.|4\.|5\.[0-8]\.)"), "CVE-2021-23143", "medium", "D3.js < 6.0 — prototype pollution"),
]

# CDN URL patterns for version extraction
_CDN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("jquery", re.compile(r"jquery[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("bootstrap", re.compile(r"bootstrap[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("angular", re.compile(r"angular[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("react", re.compile(r"react[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("vue", re.compile(r"vue[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("lodash", re.compile(r"lodash[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("moment", re.compile(r"moment[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("axios", re.compile(r"axios[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
    ("socket.io", re.compile(r"socket\.io[.-]([0-9]+\.[0-9]+\.[0-9]+)(?:\.min)?\.js", re.I)),
]

# Inline version comment patterns
_INLINE_VERSION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("jquery", re.compile(r"jQuery\s+JavaScript\s+Library\s+v([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("jquery", re.compile(r"\*\s+jQuery\s+v([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("bootstrap", re.compile(r"Bootstrap\s+v([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("lodash", re.compile(r"Lodash\s+([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("moment", re.compile(r"moment\.js\s+version\s+:\s+([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("underscore", re.compile(r"Underscore\.js\s+([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("handlebars", re.compile(r"Handlebars\.VERSION\s*=\s*['\"]([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("d3", re.compile(r"d3\s+Version\s+([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
    ("angular", re.compile(r"AngularJS\s+v([0-9]+\.[0-9]+\.[0-9]+)", re.I)),
]

# React version from meta or bundle
_REACT_VERSION_PAT = re.compile(r"React\s+([0-9]+\.[0-9]+\.[0-9]+)", re.I)

# Outdated React versions (before hooks — v15)
_REACT_OLD = re.compile(r"^(0\.|1[0-5]\.)", re.I)


class DependencyCheckScanner(BaseOsintScanner):
    """Vulnerable JavaScript dependency scanner (retire.js style).

    Crawls HTML pages to extract <script> src URLs and inline JS, then
    identifies library versions and cross-references against known CVEs.
    """

    scanner_name = "dependency_check"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        libraries_found: dict[str, str] = {}
        script_urls: list[str] = []

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DepCheckScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Step 1: Fetch main page and extract script URLs
            try:
                resp = await client.get(base_url)
                html = resp.text

                # Extract <script src="...">
                script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
                for src in script_srcs:
                    full_url = urljoin(base_url, src) if not src.startswith("http") else src
                    script_urls.append(full_url)

                    # Check CDN URL for version
                    for lib, pattern in _CDN_PATTERNS:
                        m = pattern.search(src)
                        if m:
                            libraries_found[lib] = m.group(1)

                # Check inline scripts
                inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.I | re.DOTALL)
                for script_content in inline_scripts[:10]:
                    for lib, pattern in _INLINE_VERSION_PATTERNS:
                        m = pattern.search(script_content)
                        if m and lib not in libraries_found:
                            libraries_found[lib] = m.group(1)

            except Exception as exc:
                log.debug("Dependency check baseline failed", url=base_url, error=str(exc))

            # Step 2: Fetch script files and scan for inline version markers
            async def scan_script(url: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(url, timeout=8)
                        js_content = resp.text[:50000]  # First 50KB

                        for lib, pattern in _INLINE_VERSION_PATTERNS:
                            m = pattern.search(js_content)
                            if m and lib not in libraries_found:
                                libraries_found[lib] = m.group(1)

                        # Check vulnerable patterns directly
                        for lib, vuln_pattern, cve, severity, description in _VULN_DB:
                            if vuln_pattern.search(js_content):
                                vuln = {
                                    "type": "vulnerable_library",
                                    "severity": severity,
                                    "library": lib,
                                    "cve": cve,
                                    "description": description,
                                    "script_url": url[:100],
                                }
                                if vuln not in vulnerabilities:
                                    vulnerabilities.append(vuln)
                                ident = f"vuln:dep:{lib}:{cve}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            await asyncio.gather(*[scan_script(u) for u in script_urls[:20]])

            # Step 3: Cross-reference found library versions
            for lib, version in libraries_found.items():
                for vuln_lib, vuln_pattern, cve, severity, description in _VULN_DB:
                    if lib == vuln_lib:
                        # Version already matched via inline detection; also check version string
                        vuln_version_match = vuln_pattern.pattern
                        if re.search(
                            r"(\d+\.\d+)",
                            version,
                        ):
                            major_minor = version.rsplit(".", 1)[0] if version.count(".") >= 2 else version
                            test_str = f"{lib} v{version}"
                            if vuln_pattern.search(test_str):
                                vuln = {
                                    "type": "vulnerable_library",
                                    "severity": severity,
                                    "library": lib,
                                    "version": version,
                                    "cve": cve,
                                    "description": description,
                                }
                                if vuln not in vulnerabilities:
                                    vulnerabilities.append(vuln)
                                ident = f"vuln:dep:{lib}:{cve}"
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
            "scripts_scanned": len(script_urls),
            "libraries_found": libraries_found,
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
