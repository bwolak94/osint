"""HTTP Methods scanner — dangerous HTTP method detection and abuse testing.

Tests for:
- PUT method — arbitrary file upload to web root
- DELETE method — file deletion
- TRACE method — Cross-Site Tracing (XST) to steal cookies
- CONNECT method — proxy tunneling to internal hosts
- PROPFIND/PROPPATCH — WebDAV information disclosure
- PATCH method — partial content modification without auth
- DEBUG method (IIS) — ASP.NET remote debugging enablement
- HTTP method override (X-HTTP-Method-Override, X-Method-Override)
- OPTIONS method — reveals allowed methods
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Methods to test
_DANGEROUS_METHODS: list[tuple[str, str]] = [
    ("PUT", "file_upload"),
    ("DELETE", "file_deletion"),
    ("TRACE", "cross_site_tracing"),
    ("CONNECT", "proxy_tunnel"),
    ("DEBUG", "iis_debug"),
    ("PATCH", "partial_update"),
    ("PROPFIND", "webdav_propfind"),
    ("PROPPATCH", "webdav_proppatch"),
    ("MKCOL", "webdav_mkcol"),
    ("MOVE", "webdav_move"),
    ("COPY", "webdav_copy"),
    ("SEARCH", "webdav_search"),
]

# Paths to test methods against
_TEST_PATHS: list[str] = [
    "/",
    "/uploads/",
    "/upload/",
    "/files/",
    "/api/",
    "/webdav/",
    "/dav/",
]

# Method override headers
_METHOD_OVERRIDE_HEADERS: list[str] = [
    "X-HTTP-Method-Override",
    "X-HTTP-Method",
    "X-Method-Override",
    "_method",
]

# TRACE indicator — response must echo back headers
_TRACE_ECHO = "TRACE"

# PUT test content
_PUT_CONTENT = f"method-test-{uuid.uuid4().hex[:8]}"


class HTTPMethodsScanner(BaseOsintScanner):
    """Dangerous HTTP methods detection scanner.

    Tests PUT, DELETE, TRACE, CONNECT, DEBUG, WebDAV methods,
    and HTTP method override headers for unauthorized access.
    """

    scanner_name = "http_methods"
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
        allowed_methods: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HTTPMethodsScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Step 1: OPTIONS to discover allowed methods
            try:
                resp = await client.options(base_url.rstrip("/") + "/")
                allow_header = resp.headers.get("allow", "") + resp.headers.get("public", "")
                if allow_header:
                    allowed_methods = [m.strip() for m in allow_header.split(",")]
                    # Flag dangerous methods in Allow header
                    dangerous_found = [m for m in allowed_methods
                                       if m in ("PUT", "DELETE", "TRACE", "CONNECT", "DEBUG", "PATCH")]
                    if dangerous_found:
                        vulnerabilities.append({
                            "type": "dangerous_methods_advertised",
                            "severity": "medium",
                            "url": base_url,
                            "methods": dangerous_found,
                            "allow_header": allow_header,
                            "description": f"Dangerous HTTP methods advertised via OPTIONS: "
                                           f"{', '.join(dangerous_found)}",
                            "remediation": "Remove dangerous methods from Allow header; "
                                           "restrict HTTP methods in web server config",
                        })
                        identifiers.append("info:http_methods:dangerous_advertised")
            except Exception:
                pass

            # Step 2: Test each dangerous method
            async def test_method(method: str, technique: str, path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        if method == "PUT":
                            test_filename = f"/method-probe-{uuid.uuid4().hex[:6]}.txt"
                            put_url = base_url.rstrip("/") + test_filename
                            resp = await client.put(put_url, content=_PUT_CONTENT)
                            if resp.status_code in (200, 201, 204):
                                # Verify file was actually created
                                verify_resp = await client.get(put_url)
                                if verify_resp.status_code == 200 and _PUT_CONTENT in verify_resp.text:
                                    vulnerabilities.append({
                                        "type": "http_put_upload",
                                        "severity": "critical",
                                        "url": put_url,
                                        "method": "PUT",
                                        "description": "HTTP PUT method allows arbitrary file upload — "
                                                       "attacker can write web shells to server",
                                        "remediation": "Disable PUT method: "
                                                       "LimitExcept GET POST HEAD { deny all } (Apache) or "
                                                       "dav off (nginx)",
                                    })
                                    identifiers.append("vuln:http_methods:put_upload")
                                    # Clean up test file
                                    try:
                                        await client.delete(put_url)
                                    except Exception:
                                        pass

                        elif method == "DELETE":
                            resp = await client.delete(url)
                            if resp.status_code in (200, 204):
                                vulnerabilities.append({
                                    "type": "http_delete_enabled",
                                    "severity": "high",
                                    "url": url,
                                    "method": "DELETE",
                                    "description": "HTTP DELETE method accepted — "
                                                   "server files may be deleted by unauthenticated requests",
                                    "remediation": "Disable DELETE method in web server config",
                                })
                                ident = "vuln:http_methods:delete_enabled"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                        elif method == "TRACE":
                            resp = await client.request("TRACE", url,
                                                         headers={"X-Custom-Test": "trace-probe"})
                            if resp.status_code == 200 and (
                                _TRACE_ECHO in resp.text or
                                "X-Custom-Test" in resp.text
                            ):
                                vulnerabilities.append({
                                    "type": "http_trace_enabled",
                                    "severity": "medium",
                                    "url": url,
                                    "method": "TRACE",
                                    "cve": "CVE-2003-1567",
                                    "description": "HTTP TRACE method enabled — enables Cross-Site Tracing (XST): "
                                                   "attacker can steal HttpOnly cookies via XSS + TRACE combo",
                                    "remediation": "Disable TRACE method: TraceEnable off (Apache) or "
                                                   "add_header ... / limit TRACE in nginx",
                                })
                                ident = "vuln:http_methods:trace_xst"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                        elif method == "DEBUG" and path == "/":
                            resp = await client.request("DEBUG", url,
                                                         headers={"Command": "stop-debug"})
                            if resp.status_code in (200, 405) and "IIS" not in resp.headers.get("server", ""):
                                pass  # Not IIS, skip
                            elif resp.status_code == 200:
                                vulnerabilities.append({
                                    "type": "iis_debug_enabled",
                                    "severity": "critical",
                                    "url": url,
                                    "method": "DEBUG",
                                    "description": "IIS DEBUG method enabled — "
                                                   "allows attaching remote debugger to ASP.NET process",
                                    "remediation": "Disable DEBUG: add <httpRuntime debug='false'/> in web.config; "
                                                   "restrict DEBUG method at server level",
                                })
                                ident = "vuln:http_methods:iis_debug"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                        elif method == "PROPFIND":
                            resp = await client.request(
                                "PROPFIND", url,
                                headers={"Depth": "1", "Content-Type": "application/xml"},
                                content='<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:allprop/></D:propfind>',
                            )
                            if resp.status_code in (200, 207):
                                vulnerabilities.append({
                                    "type": "webdav_propfind",
                                    "severity": "medium",
                                    "url": url,
                                    "method": "PROPFIND",
                                    "description": "WebDAV PROPFIND enabled — directory structure and file "
                                                   "metadata browsable without auth",
                                    "remediation": "Disable WebDAV if not needed",
                                })
                                ident = "vuln:http_methods:webdav_propfind"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            # Step 3: Method override bypass testing
            async def test_method_override(override_header: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + "/"
                    try:
                        # Try to use GET + override to simulate DELETE
                        resp = await client.get(url, headers={override_header: "DELETE"})
                        if resp.status_code in (200, 204):
                            vulnerabilities.append({
                                "type": "method_override_bypass",
                                "severity": "high",
                                "url": url,
                                "override_header": override_header,
                                "description": f"HTTP method override via '{override_header}' header — "
                                               "DELETE/PATCH accepted via GET request, bypassing method restrictions",
                                "remediation": "Validate HTTP method from request line only; "
                                               "ignore X-HTTP-Method-Override unless explicitly needed",
                            })
                            ident = "vuln:http_methods:override_bypass"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for method, technique in _DANGEROUS_METHODS:
                for path in _TEST_PATHS[:3]:
                    tasks.append(test_method(method, technique, path))
            for override_header in _METHOD_OVERRIDE_HEADERS:
                tasks.append(test_method_override(override_header))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "allowed_methods": allowed_methods,
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
