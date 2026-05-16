"""Dalfox — advanced XSS vulnerability scanner.

Dalfox is a powerful parameter analysis and XSS scanning tool. It finds
reflected, stored, and DOM-based XSS vulnerabilities with context-aware
payload generation.

Two-mode operation:
1. **dalfox binary** — if on PATH, full XSS scanning with JSON output
2. **Manual fallback** — HTTP-based XSS reflection checks using probe payloads
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse, parse_qs, urlunparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# XSS probe payloads — designed to be detectable without being destructive
_XSS_PROBES: list[tuple[str, str]] = [
    # (payload, detection_pattern)
    ('<script>alert(1)</script>', r'<script>alert\(1\)</script>'),
    ('"<xss>', r'"<xss>'),
    ("'<xss>", r"'<xss>"),
    ('<img src=x onerror=1>', r'<img src=x onerror=1>'),
    ('javascript:alert(1)', r'javascript:alert\(1\)'),
    ('<svg/onload=1>', r'<svg/onload=1>'),
    ('"><script>1</script>', r'"><script>1</script>'),
    ("'><svg onload=1>", r"'><svg onload=1>"),
]

# Common XSS injection parameters
_XSS_PARAMS: list[str] = [
    "q", "query", "search", "s", "keyword", "term",
    "input", "text", "message", "comment",
    "redirect", "url", "next", "return", "ref",
    "name", "title", "description",
    "id", "user", "username",
    "callback", "jsonp",
    "lang", "locale", "format",
    "page", "path", "file",
]

# Context patterns to identify where input is reflected
_REFLECTION_CONTEXTS = {
    "html_attribute": re.compile(r'(?i)(?:value|placeholder|title|alt|href)=["\'][^"\']*MARKER'),
    "html_body": re.compile(r'(?i)>([^<]*MARKER[^<]*)<'),
    "javascript_var": re.compile(r'(?i)(?:var|let|const)\s+\w+\s*=\s*["\']?[^"\';\n]*MARKER'),
    "url_param": re.compile(r'(?i)[?&]\w+=([^&]*MARKER[^&]*)'),
}


class DalfoxScanner(BaseOsintScanner):
    """Advanced XSS vulnerability scanner.

    Tests URL parameters for reflected XSS vulnerabilities using context-aware
    payload detection. Identifies the reflection context (HTML body, attribute,
    JavaScript variable, URL parameter) to assess exploitability.
    """

    scanner_name = "dalfox"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("dalfox"):
            return await self._run_dalfox_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_dalfox_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"dalfox_{run_id}.json")
        cmd = [
            "dalfox",
            "url",
            base_url,
            "--format", "json",
            "--output", out_file,
            "--no-color",
            "--silence",
            "--timeout", "10",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("dalfox timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        vulnerabilities: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                for item in data if isinstance(data, list) else []:
                    vulnerabilities.append({
                        "type": item.get("type", "XSS"),
                        "url": item.get("poc", base_url),
                        "parameter": item.get("param", ""),
                        "payload": item.get("payload", ""),
                        "evidence": item.get("evidence", ""),
                        "severity": "high",
                    })
            except Exception as exc:
                log.warning("Failed to parse dalfox output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"vuln:xss:{v['parameter']}" for v in vulnerabilities if v.get("parameter")]
        return {
            "input": input_value,
            "scan_mode": "dalfox_binary",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        reflection_findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; XSSScanner/1.0)"},
        ) as client:
            # Baseline — check existing params in URL
            parsed = urlparse(base_url)
            existing_params = list(parse_qs(parsed.query).keys())
            test_params = list(set(existing_params + _XSS_PARAMS[:10]))

            semaphore = asyncio.Semaphore(8)

            async def test_param(param: str) -> None:
                async with semaphore:
                    for payload, pattern in _XSS_PROBES[:4]:  # Test top 4 payloads
                        try:
                            test_url = f"{base_url}?{param}={payload}"
                            resp = await client.get(test_url)
                            body = resp.text

                            # Check if payload is reflected unencoded
                            if re.search(re.escape(payload), body, re.I):
                                # Determine reflection context
                                context = "unknown"
                                marker = payload
                                for ctx_name, ctx_pattern in _REFLECTION_CONTEXTS.items():
                                    if ctx_pattern.search(body.replace(payload, f"MARKER_{param}")):
                                        context = ctx_name
                                        break

                                finding = {
                                    "parameter": param,
                                    "payload": payload,
                                    "url": test_url,
                                    "reflection_context": context,
                                    "status_code": resp.status_code,
                                    "severity": "high" if context != "url_param" else "medium",
                                    "type": "reflected_xss",
                                }
                                vulnerabilities.append(finding)
                                ident = f"vuln:xss:{param}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                break  # One confirmed vulnerability per param is enough

                            # Check for partial reflection (HTML encoding bypasses)
                            elif payload.replace("<", "&lt;") in body or payload.replace(">", "&gt;") in body:
                                reflection_findings.append({
                                    "parameter": param,
                                    "payload": payload,
                                    "url": test_url,
                                    "note": "Payload reflected but HTML-encoded — potential DOM XSS",
                                    "type": "encoded_reflection",
                                    "severity": "info",
                                })
                        except Exception:
                            pass

            tasks = [test_param(p) for p in test_params]
            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "reflection_findings": reflection_findings,
            "total_vulnerabilities": len(vulnerabilities),
            "total_reflections": len(reflection_findings),
            "params_tested": test_params if 'test_params' in dir() else [],
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
