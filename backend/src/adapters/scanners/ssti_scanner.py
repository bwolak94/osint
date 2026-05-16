"""SSTI — Server-Side Template Injection scanner.

SSTI allows attackers to inject template directives into server-side
template engines, leading to RCE. Affects Jinja2 (Python), Twig (PHP),
Freemarker (Java), Pebble, Velocity, Smarty, Mako, and others.

Detects via mathematical expression evaluation ({{7*7}} → 49).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SSTI detection probes: (payload, expected_result, engine_hint)
# All probes are arithmetic — no destructive operations
_SSTI_PROBES: list[tuple[str, str, str]] = [
    # Jinja2 / Twig / Django Templates
    ("{{7*7}}", "49", "jinja2_twig"),
    ("${7*7}", "49", "freemarker_el"),
    ("#{7*7}", "49", "pebble_thymeleaf"),
    ("<%=7*7%>", "49", "erb_mako"),
    ("{7*7}", "49", "smarty"),
    ("*{7*7}", "49", "thymeleaf_spel"),
    ("[[${7*7}]]", "49", "thymeleaf"),
    ("{#7*7#}", "49", "nunjucks"),
    # Jinja2 string confirm
    ("{{7*'7'}}", "7777777", "jinja2"),
    # Velocity/Freemarker
    ("#set($a=7*7)$a", "49", "velocity"),
    ("${7*7}", "49", "freemarker"),
    # ERB (Ruby)
    ("<%= 7 * 7 %>", "49", "erb"),
    # Mako (Python)
    ("${7*7}", "49", "mako"),
    # Handlebars (JS)
    ("{{#with 7}}{{multiply 7 this}}{{/with}}", "49", "handlebars"),
]

# Confirmation probes for identified engines
_ENGINE_CONFIRM: dict[str, list[tuple[str, str]]] = {
    "jinja2": [
        ("{{config}}", "Config|SECRET"),
        ("{{7*'7'}}", "7777777"),
        ('{{"".__class__}}', "str|class"),
    ],
    "twig": [
        ("{{7*7}}", "49"),
        ("{{_self.env}}", "Environment"),
    ],
    "freemarker": [
        ("${7*7}", "49"),
        ("${\"freemarker\".toUpperCase()}", "FREEMARKER"),
    ],
}

# Common template injection parameters
_SSTI_PARAMS: list[str] = [
    "name", "title", "message", "template", "content",
    "text", "subject", "body", "greeting", "page",
    "query", "search", "input", "value", "data",
    "username", "user", "email", "comment", "feedback",
    "lang", "locale", "format", "output",
]


class SSTIScanner(BaseOsintScanner):
    """Server-Side Template Injection vulnerability scanner.

    Tests parameters for SSTI vulnerabilities across all major template
    engines. Uses mathematical probe expressions ({{7*7}}) to detect
    execution without destructive payloads. Identifies the specific
    template engine when possible.
    """

    scanner_name = "ssti"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]
        test_params = list(dict.fromkeys(existing_params + _SSTI_PARAMS[:10]))

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SSTIScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            async def test_param(param: str) -> None:
                async with semaphore:
                    for payload, expected, engine_hint in _SSTI_PROBES:
                        try:
                            # GET
                            resp = await client.get(f"{base_clean}?{param}={payload}")
                            if expected in resp.text:
                                engine = _identify_engine(resp.text, payload, engine_hint)
                                vuln = {
                                    "parameter": param,
                                    "payload": payload,
                                    "expected": expected,
                                    "method": "GET",
                                    "template_engine": engine,
                                    "severity": "critical",
                                    "description": f"SSTI: expression '{payload}' evaluated to '{expected}'",
                                }
                                vulnerabilities.append(vuln)
                                identifiers.append(f"vuln:ssti:{param}:{engine}")
                                return  # Confirmed for this param

                            # POST
                            resp = await client.post(base_clean, data={param: payload})
                            if expected in resp.text:
                                engine = _identify_engine(resp.text, payload, engine_hint)
                                vuln = {
                                    "parameter": param,
                                    "payload": payload,
                                    "expected": expected,
                                    "method": "POST",
                                    "template_engine": engine,
                                    "severity": "critical",
                                    "description": f"SSTI via POST: '{payload}' → '{expected}'",
                                }
                                vulnerabilities.append(vuln)
                                identifiers.append(f"vuln:ssti:{param}:{engine}")
                                return

                        except Exception:
                            pass

            await asyncio.gather(*[test_param(p) for p in test_params])

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "engines_detected": list({v.get("template_engine", "unknown") for v in vulnerabilities}),
            "params_tested": test_params,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _identify_engine(body: str, payload: str, hint: str) -> str:
    """Try to narrow down the template engine from response characteristics."""
    if "{{7*'7'}}" in payload and "7777777" in body:
        return "Jinja2"
    if "jinja2_twig" in hint:
        if re.search(r"jinja|flask|werkzeug", body, re.I):
            return "Jinja2"
        if re.search(r"twig|symfony|laravel", body, re.I):
            return "Twig"
        return "Jinja2/Twig"
    if "freemarker" in hint:
        return "Freemarker"
    if "erb" in hint:
        return "ERB (Ruby)"
    if "velocity" in hint:
        return "Velocity"
    return hint.replace("_", "/").title()


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
