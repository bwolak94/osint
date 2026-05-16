"""HTTP Request Smuggling — desync vulnerability scanner.

HTTP request smuggling exploits discrepancies between how front-end (CDN/proxy)
and back-end servers parse HTTP/1.1 Transfer-Encoding and Content-Length headers.
Critical for bypassing access controls, stealing credentials, and cache poisoning.

Techniques tested:
- CL.TE (Content-Length front, Transfer-Encoding backend)
- TE.CL (Transfer-Encoding front, Content-Length backend)
- TE.TE obfuscation (both support TE but one ignores obfuscated headers)
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# TE obfuscation variants that confuse parsers
_TE_OBFUSCATIONS: list[str] = [
    "Transfer-Encoding: xchunked",
    "Transfer-Encoding: chunked, identity",
    "Transfer-Encoding :\nchunked",
    "Transfer-Encoding: chunked\r\nTransfer-Encoding: x",
    "X: X\nTransfer-Encoding: chunked",
    " Transfer-Encoding: chunked",
    "Transfer-Encoding: chunked",
]


class HTTPSmugglingScanner(BaseOsintScanner):
    """HTTP request smuggling / desync vulnerability scanner.

    Tests for CL.TE, TE.CL, and TE.TE obfuscation desync issues.
    Uses time-based detection to identify potential smuggling endpoints
    without affecting normal traffic.
    """

    scanner_name = "http_smuggling"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        findings: list[dict[str, Any]] = []

        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        is_https = parsed.scheme == "https"

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=False,
            verify=False,
            http1=True,
            http2=False,  # Smuggling is HTTP/1.1 only
            headers={"User-Agent": "Mozilla/5.0 (compatible; SmugglingScanner/1.0)"},
        ) as client:

            # 1. CL.TE detection — send CL that front-end trusts, TE that backend uses
            # If backend parses TE=chunked, the extra data becomes a prefix for next request
            try:
                t0 = time.monotonic()
                resp = await client.post(
                    base_url,
                    content=b"0\r\n\r\nG",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Content-Length": "6",
                        "Transfer-Encoding": "chunked",
                    },
                )
                elapsed = time.monotonic() - t0
                # CL.TE: if backend uses TE, it waits for chunk terminator
                # Fast response = possible CL.TE; timeout/slow = confirmed
                findings.append({
                    "technique": "CL.TE",
                    "response_time": round(elapsed, 2),
                    "status_code": resp.status_code,
                    "suspect": elapsed > 5.0,
                })
                if elapsed > 5.0:
                    vuln = {
                        "technique": "CL.TE",
                        "severity": "critical",
                        "evidence": f"Response delayed {elapsed:.1f}s — possible CL.TE desync",
                        "description": "Front-end uses Content-Length, back-end uses Transfer-Encoding",
                    }
                    vulnerabilities.append(vuln)
                    identifiers.append("vuln:http_smuggling:cl_te")
            except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                findings.append({
                    "technique": "CL.TE",
                    "response_time": 12.0,
                    "error": "timeout",
                    "suspect": True,
                })
                vulnerabilities.append({
                    "technique": "CL.TE",
                    "severity": "high",
                    "evidence": "Request timed out — possible CL.TE desync",
                    "description": "Server stopped reading after Content-Length bytes, leaving TE chunk data",
                })
                identifiers.append("vuln:http_smuggling:cl_te_timeout")
            except Exception:
                pass

            # 2. TE.CL detection
            try:
                t0 = time.monotonic()
                te_cl_body = b"5\r\nSMUGG\r\n0\r\n\r\n"
                resp = await client.post(
                    base_url,
                    content=te_cl_body,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Content-Length": str(len(te_cl_body) + 10),  # Intentionally wrong
                        "Transfer-Encoding": "chunked",
                    },
                )
                elapsed = time.monotonic() - t0
                findings.append({
                    "technique": "TE.CL",
                    "response_time": round(elapsed, 2),
                    "status_code": resp.status_code,
                    "suspect": resp.status_code in (400, 408, 500) or elapsed > 5.0,
                })
                if resp.status_code == 400 and elapsed < 3.0:
                    # Quick 400 with wrong CL can indicate TE.CL
                    vuln = {
                        "technique": "TE.CL",
                        "severity": "high",
                        "evidence": f"HTTP 400 with mismatched CL — possible TE.CL desync",
                        "description": "Front-end uses Transfer-Encoding, back-end uses Content-Length",
                    }
                    vulnerabilities.append(vuln)
                    identifiers.append("vuln:http_smuggling:te_cl")
            except Exception:
                pass

            # 3. TE.TE obfuscation test — check for differential behaviour
            te_responses: dict[str, int] = {}
            for te_header in _TE_OBFUSCATIONS[:4]:
                try:
                    header_name, header_val = te_header.split(": ", 1)
                    resp = await client.post(
                        base_url,
                        content=b"0\r\n\r\n",
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Content-Length": "5",
                            header_name.strip(): header_val.strip(),
                        },
                    )
                    te_responses[te_header[:30]] = resp.status_code
                except Exception:
                    pass

            # Differential: if responses differ significantly across TE variants
            unique_status_codes = set(te_responses.values())
            if len(unique_status_codes) > 1:
                findings.append({
                    "technique": "TE.TE",
                    "differential_responses": te_responses,
                    "suspect": True,
                })
                vulnerabilities.append({
                    "technique": "TE.TE_obfuscation",
                    "severity": "high",
                    "evidence": f"Differential responses to TE variants: {unique_status_codes}",
                    "description": "Different TE header obfuscations produce different responses — possible TE.TE desync",
                })
                identifiers.append("vuln:http_smuggling:te_te")

            # 4. Check HTTP version and connection headers for risk indicators
            try:
                resp = await client.get(base_url)
                via = resp.headers.get("Via", "")
                x_forwarded = resp.headers.get("X-Forwarded-For", "")
                if via:
                    findings.append({
                        "technique": "proxy_detection",
                        "via_header": via,
                        "note": "Multi-layer proxy detected — higher smuggling risk",
                    })
            except Exception:
                pass

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "probe_results": findings,
            "total_vulnerabilities": len(vulnerabilities),
            "is_vulnerable": len(vulnerabilities) > 0,
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
