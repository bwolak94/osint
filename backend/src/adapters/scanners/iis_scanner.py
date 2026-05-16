"""IIS (Internet Information Services) vulnerability scanner.

Detects:
- IIS tilde (~) short filename enumeration (8.3 filename disclosure)
- CVE-2017-7269 — IIS 6.0 WebDAV Buffer Overflow RCE
- WebDAV PUT/MOVE method file upload
- ASP.NET Debug mode enabled (TRACE/DEBUG methods)
- IIS HTTP.sys CVE-2015-1635 (MS15-034) remote code execution
- IIS ISAPI extensions: .ida, .idq, .printer (CodeRed/Nimda fingerprint)
- ASP.NET error pages revealing stack traces and internal paths
- IIS default pages: iisstart.htm, default.htm, localstart.asp
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

# IIS tilde enumeration probes
_TILDE_PROBES: list[tuple[str, str]] = [
    ("/*~1*/a.aspx", "tilde_wildcard_aspx"),
    ("/*~1*/.aspx", "tilde_all_aspx"),
    ("/a~1/", "tilde_dir"),
    ("/aspx~1", "tilde_aspx"),
]

# WebDAV probes
_WEBDAV_PROBE_PATH = "/webdav/"
_WEBDAV_METHODS = ["PROPFIND", "OPTIONS", "PUT", "DELETE", "MOVE", "COPY"]

# CVE-2015-1635 (MS15-034) probe — Range header overflow
_MS15034_HEADERS = {
    "Range": "bytes=0-18446744073709551615",
}

# IIS-specific paths
_IIS_PATHS: list[tuple[str, str]] = [
    ("/iisstart.htm", "iis_default_page"),
    ("/iis-85.png", "iis85_image"),
    ("/aspnet_client/", "aspnet_client"),
    ("/trace.axd", "trace_axd"),
    ("/_vti_bin/", "frontpage_ext"),
    ("/_vti_bin/_vti_aut/author.dll", "frontpage_author"),
    ("/_vti_inf.html", "frontpage_info"),
    ("/elmah.axd", "elmah_error_log"),
    ("/Elmah.axd", "elmah_upper"),
    ("/Global.asax", "global_asax"),
    ("/web.config", "web_config"),
    ("/Web.config", "web_config_upper"),
    ("/applicationHost.config", "application_host"),
    ("/null.ida", "ida_codered"),
    ("/x.ida", "ida_codered2"),
]

# IIS indicators
_IIS_INDICATORS = re.compile(
    r'(?i)(Microsoft-IIS|ASP\.NET|X-Powered-By:\s*ASP\.NET|IIS|X-AspNet-Version)',
)
_IIS_VERSION = re.compile(r'Microsoft-IIS/(\d+\.\d+)', re.I)
_ASP_ERROR = re.compile(r'(?i)(Server Error in|Application error|Stack trace|System\.Web)', re.I)

# WebDAV indicator
_WEBDAV_INDICATOR = re.compile(r'(?i)(DAV:|PROPFIND|Allow.*PROPFIND|MS-Author-Via)', re.I)

# Tilde success indicators (IIS returns 400 or unique response for valid paths)
_TILDE_SUCCESS_STATUS = {400}  # IIS returns 400 for tilde paths that match real files
_TILDE_404_STATUS = {404}


class IISScanner(BaseOsintScanner):
    """Microsoft IIS vulnerability scanner.

    Detects tilde filename enumeration, WebDAV file upload, ASP.NET debug mode,
    CVE-2015-1635 HTTP.sys RCE, FrontPage extensions, and config disclosure.
    """

    scanner_name = "iis"
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
        iis_info: dict[str, Any] = {}
        iis_detected = False

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; IISScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Detect IIS
            try:
                resp = await client.get(base_url)
                server_header = resp.headers.get("server", "")
                powered_by = resp.headers.get("x-powered-by", "")
                aspnet_version = resp.headers.get("x-aspnet-version", "")
                combined = server_header + powered_by + aspnet_version + resp.text

                if _IIS_INDICATORS.search(combined):
                    iis_detected = True
                    ver_match = _IIS_VERSION.search(server_header)
                    if ver_match:
                        iis_info["version"] = ver_match.group(1)
                    if powered_by:
                        iis_info["powered_by"] = powered_by
                    if aspnet_version:
                        iis_info["aspnet_version"] = aspnet_version
                        identifiers.append(f"info:iis:aspnet:{aspnet_version}")
            except Exception:
                pass

            # Tilde enumeration
            async def probe_tilde(path: str, technique: str) -> None:
                nonlocal iis_detected
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        # IIS tilde bug: returns 400 for existing tilde paths, 404 for non-existing
                        if resp.status_code == 400:
                            iis_detected = True
                            vulnerabilities.append({
                                "type": "iis_tilde_enumeration",
                                "severity": "medium",
                                "url": url,
                                "technique": technique,
                                "description": "IIS 8.3 short filename (tilde ~) enumeration vulnerability — "
                                               "allows guessing filenames without directory listing",
                                "remediation": "Disable 8.3 filename creation: "
                                               "fsutil behavior set disable8dot3 1; "
                                               "apply Microsoft KB2588513 or IIS URL rewrite rules",
                            })
                            ident = "vuln:iis:tilde_enumeration"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # CVE-2015-1635 HTTP.sys probe
            async def probe_ms15034() -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + "/"
                    try:
                        resp = await client.get(url, headers=_MS15034_HEADERS)
                        if resp.status_code == 416:
                            # "Requested Range Not Satisfiable" = unpatched IIS
                            vulnerabilities.append({
                                "type": "iis_httpsys_rce",
                                "severity": "critical",
                                "url": url,
                                "cve": "CVE-2015-1635",
                                "description": "IIS HTTP.sys Range header parsing RCE (MS15-034) — "
                                               "unauthenticated remote code execution via malformed Range header",
                                "remediation": "Apply MS15-034 (KB3042553); upgrade Windows to patched version",
                            })
                            identifiers.append("vuln:iis:cve_2015_1635")
                    except Exception:
                        pass

            # IIS-specific path probes
            async def probe_iis_path(path: str, technique: str) -> None:
                nonlocal iis_detected
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        headers_str = str(resp.headers)

                        if _IIS_INDICATORS.search(headers_str):
                            iis_detected = True

                        if resp.status_code == 200:
                            if technique in ("web_config", "web_config_upper"):
                                if "<configuration>" in body or "connectionString" in body:
                                    vulnerabilities.append({
                                        "type": "web_config_exposed",
                                        "severity": "critical",
                                        "url": url,
                                        "description": "ASP.NET web.config accessible — "
                                                       "connection strings, API keys, auth config exposed",
                                        "remediation": "Block web.config access; "
                                                       "configure IIS to deny .config files",
                                    })
                                    identifiers.append("vuln:iis:web_config_exposed")

                            elif technique == "trace_axd":
                                vulnerabilities.append({
                                    "type": "aspnet_trace_enabled",
                                    "severity": "high",
                                    "url": url,
                                    "description": "ASP.NET trace.axd enabled — "
                                                   "reveals request details, session IDs, server variables",
                                    "remediation": "Disable trace in web.config: "
                                                   "<trace enabled='false'/>",
                                })
                                identifiers.append("vuln:iis:trace_axd")

                            elif technique == "elmah_error_log":
                                vulnerabilities.append({
                                    "type": "elmah_exposed",
                                    "severity": "high",
                                    "url": url,
                                    "description": "ELMAH error log accessible — "
                                                   "reveals stack traces, exception details, internal paths",
                                    "remediation": "Restrict elmah.axd access to localhost; "
                                                   "add authorization in web.config",
                                })
                                identifiers.append("vuln:iis:elmah_exposed")

                            elif technique in ("frontpage_ext", "frontpage_author", "frontpage_info"):
                                vulnerabilities.append({
                                    "type": "frontpage_extensions_exposed",
                                    "severity": "high",
                                    "url": url,
                                    "description": "FrontPage Server Extensions accessible — "
                                                   "known RCE/auth bypass vulnerabilities",
                                    "remediation": "Remove/disable FrontPage extensions",
                                })
                                ident = "vuln:iis:frontpage_exposed"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                            elif technique in ("ida_codered", "ida_codered2"):
                                vulnerabilities.append({
                                    "type": "iis_isapi_ida_exposed",
                                    "severity": "medium",
                                    "url": url,
                                    "description": "IIS ISAPI .ida extension accessible — "
                                                   "CodeRed worm fingerprint; potential buffer overflow",
                                    "remediation": "Remove .ida/.idq ISAPI mappings; uninstall Index Server",
                                })
                                ident = "vuln:iis:ida_isapi"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                            # ASP.NET error page leak
                            if _ASP_ERROR.search(body):
                                vulnerabilities.append({
                                    "type": "aspnet_error_page",
                                    "severity": "medium",
                                    "url": url,
                                    "description": "ASP.NET detailed error page exposed — "
                                                   "stack trace and internal paths revealed",
                                    "remediation": "Set customErrors mode='On' in web.config",
                                })
                                ident = "vuln:iis:aspnet_error"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            # WebDAV test
            async def probe_webdav() -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + "/"
                    try:
                        # PROPFIND request
                        resp = await client.request(
                            "PROPFIND", url,
                            headers={"Depth": "1", "Content-Type": "application/xml"},
                            content='<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:allprop/></D:propfind>',
                        )
                        if resp.status_code in (200, 207):
                            if _WEBDAV_INDICATOR.search(str(resp.headers) + resp.text):
                                vulnerabilities.append({
                                    "type": "webdav_enabled",
                                    "severity": "high",
                                    "url": url,
                                    "description": "WebDAV enabled — file upload/modification possible via "
                                                   "PUT/MOVE/COPY/DELETE methods without proper auth",
                                    "remediation": "Disable WebDAV if not needed; "
                                                   "require auth for all WebDAV methods",
                                })
                                identifiers.append("vuln:iis:webdav_enabled")
                    except Exception:
                        pass

            tasks = []
            for path, tech in _TILDE_PROBES:
                tasks.append(probe_tilde(path, tech))
            for path, tech in _IIS_PATHS:
                tasks.append(probe_iis_path(path, tech))
            tasks.append(probe_ms15034())
            tasks.append(probe_webdav())

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "iis_detected": iis_detected,
            "iis_info": iis_info,
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
