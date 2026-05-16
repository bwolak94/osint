"""Corsy — CORS misconfiguration scanner.

Corsy identifies misconfigurations in Cross-Origin Resource Sharing (CORS) policies.
A misconfigured CORS policy can allow attackers to read sensitive data across origins.

Two-mode operation:
1. **corsy binary** — if on PATH, invoked for full CORS analysis
2. **Manual fallback** — sends crafted Origin headers and analyses CORS responses
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# CORS attack test origins — checks for various bypass techniques
_TEST_ORIGINS: list[tuple[str, str]] = [
    # (test_origin, test_type)
    ("null", "null_origin"),
    ("https://evil.com", "arbitrary_origin"),
    ("https://evil.{target}", "subdomain_reflection"),
    ("https://{target}.evil.com", "prefix_reflection"),
    ("https://{target}evil.com", "suffix_bypass"),
    ("http://{target}", "http_downgrade"),
    ("https://{target_with_port}", "port_variation"),
    ("https://not-{target}", "invalid_subdomain"),
]

# CORS header names to inspect
_CORS_HEADERS = [
    "Access-Control-Allow-Origin",
    "Access-Control-Allow-Credentials",
    "Access-Control-Allow-Methods",
    "Access-Control-Allow-Headers",
    "Access-Control-Expose-Headers",
    "Access-Control-Max-Age",
    "Vary",
]


class CorsyScanner(BaseOsintScanner):
    """CORS misconfiguration scanner.

    Tests for insecure CORS configurations including:
    - Wildcard with credentials (critical)
    - Arbitrary origin reflection
    - Null origin trust
    - Prefix/suffix reflection bypasses
    - HTTP downgrade allowing
    Identifies which origins can read sensitive responses.
    """

    scanner_name = "corsy"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("corsy"):
            return await self._run_corsy_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_corsy_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"corsy_{run_id}.json")
        cmd = [
            "corsy",
            "-u", base_url,
            "-o", out_file,
            "--json",
            "-q",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 5)
        except asyncio.TimeoutError:
            log.warning("corsy timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        findings: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                for url_key, result in (data.items() if isinstance(data, dict) else []):
                    if result.get("class"):
                        findings.append({
                            "url": url_key,
                            "class": result.get("class"),
                            "origin": result.get("origin"),
                            "credentials": result.get("credentials"),
                            "severity": _classify_severity(result.get("class", "")),
                        })
            except Exception as exc:
                log.warning("Failed to parse corsy output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"vuln:cors:{f['class']}" for f in findings if f.get("class")]
        return {
            "input": input_value,
            "scan_mode": "corsy_binary",
            "base_url": base_url,
            "cors_findings": findings,
            "total_findings": len(findings),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        cors_headers_found: dict[str, str] = {}
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        target_domain = parsed.hostname or ""
        target_port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CORSScanner/1.0)"},
        ) as client:
            for test_origin_tmpl, test_type in _TEST_ORIGINS:
                # Build the test origin
                test_origin = (
                    test_origin_tmpl
                    .replace("{target}", target_domain)
                    .replace("{target_with_port}", f"{target_domain}{target_port}")
                )

                try:
                    resp = await client.get(
                        base_url,
                        headers={"Origin": test_origin},
                    )

                    acao = resp.headers.get("Access-Control-Allow-Origin", "")
                    acac = resp.headers.get("Access-Control-Allow-Credentials", "").lower()

                    # Collect CORS headers on first successful request
                    if not cors_headers_found:
                        for h in _CORS_HEADERS:
                            val = resp.headers.get(h, "")
                            if val:
                                cors_headers_found[h] = val

                    # --- Vulnerability checks ---

                    # 1. Wildcard with credentials (impossible per spec, but misconfigured proxies)
                    if acao == "*" and acac == "true":
                        vuln = {
                            "type": "wildcard_with_credentials",
                            "severity": "critical",
                            "origin_sent": test_origin,
                            "acao_received": acao,
                            "credentials": True,
                            "description": "Wildcard ACAO with credentials=true — browsers block this but servers shouldn't allow it",
                        }
                        vulnerabilities.append(vuln)
                        identifiers.append("vuln:cors:wildcard_with_credentials")

                    # 2. Origin reflected back (arbitrary origin trust)
                    elif acao == test_origin and test_origin not in ("null",):
                        severity = "critical" if acac == "true" else "medium"
                        description = (
                            f"CORS arbitrary origin reflection with credentials"
                            if acac == "true"
                            else f"CORS arbitrary origin reflection (no credentials)"
                        )
                        vuln = {
                            "type": f"origin_reflection_{test_type}",
                            "severity": severity,
                            "origin_sent": test_origin,
                            "acao_received": acao,
                            "credentials": acac == "true",
                            "description": description,
                        }
                        vulnerabilities.append(vuln)
                        ident = f"vuln:cors:{test_type}"
                        if ident not in identifiers:
                            identifiers.append(ident)

                    # 3. Null origin accepted
                    elif test_origin == "null" and acao == "null":
                        severity = "high" if acac == "true" else "low"
                        vuln = {
                            "type": "null_origin_trusted",
                            "severity": severity,
                            "origin_sent": "null",
                            "acao_received": acao,
                            "credentials": acac == "true",
                            "description": "Null origin is trusted — exploitable via sandboxed iframes",
                        }
                        vulnerabilities.append(vuln)
                        identifiers.append("vuln:cors:null_origin")

                    # 4. Wildcard only (no credentials — low risk)
                    elif acao == "*" and not cors_headers_found:
                        cors_headers_found["note"] = "Wildcard ACAO without credentials (acceptable for public APIs)"

                except Exception as exc:
                    log.debug("CORS probe failed", origin=test_origin_tmpl, error=str(exc))

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "cors_headers": cors_headers_found,
            "vulnerabilities": vulnerabilities,
            "total_vulnerabilities": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _classify_severity(cors_class: str) -> str:
    cors_class = cors_class.lower()
    if "reflect" in cors_class or "trusted" in cors_class:
        return "critical"
    if "null" in cors_class or "wildcard" in cors_class:
        return "high"
    return "medium"


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
