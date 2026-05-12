"""API Security Scanner — tests for OWASP API Top 10 vulnerabilities.

Module 107 in the Infrastructure & Exploitation domain. Probes the target URL/domain
for common API security issues including exposed API documentation (Swagger/OpenAPI),
BOLA indicators via object ID enumeration, unauthenticated endpoint exposure, and
mass assignment hints in response structures. Maps findings to OWASP API Top 10 (2023).
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

# Common API documentation paths (OWASP API9:2023 — Improper Inventory Management)
_API_DOC_PATHS = [
    "/api/docs",
    "/api/v1/docs",
    "/api/v2/docs",
    "/swagger",
    "/swagger-ui",
    "/swagger-ui.html",
    "/swagger.json",
    "/swagger.yaml",
    "/swagger/v1/swagger.json",
    "/openapi.json",
    "/openapi.yaml",
    "/api-docs",
    "/api/swagger.json",
    "/redoc",
    "/graphql",
    "/v1/api-docs",
    "/v2/api-docs",
]

# Common unauthenticated API patterns (OWASP API1:2023 — Broken Object Level Authorization)
_BOLA_PROBE_PATHS = [
    "/api/users/1",
    "/api/users/2",
    "/api/v1/users/1",
    "/api/v1/users/2",
    "/api/accounts/1",
    "/api/items/1",
    "/api/orders/1",
]

_MASS_ASSIGNMENT_KEYWORDS = ["is_admin", "role", "admin", "permissions", "is_superuser", "scope", "tier"]


def _normalize_base(input_value: str) -> str:
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}"


def _classify_owasp(path: str, finding_type: str) -> str:
    """Map a finding to its OWASP API Top 10 category."""
    mapping: dict[str, str] = {
        "swagger": "API9:2023 - Improper Inventory Management",
        "openapi": "API9:2023 - Improper Inventory Management",
        "docs": "API9:2023 - Improper Inventory Management",
        "bola": "API1:2023 - Broken Object Level Authorization",
        "mass_assignment": "API3:2023 - Broken Object Property Level Authorization",
        "unauth": "API2:2023 - Broken Authentication",
        "graphql": "API9:2023 - Improper Inventory Management",
    }
    return mapping.get(finding_type, "API9:2023 - Improper Inventory Management")


class APISecurityScanner(BaseOsintScanner):
    """Tests target APIs for OWASP API Top 10 issues.

    Checks for exposed API documentation, unauthenticated endpoint access,
    BOLA via sequential ID probing, and mass assignment indicators in JSON
    response structures. Maps each finding to its OWASP API category (Module 107).
    """

    scanner_name = "api_security_scanner"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.DOMAIN})
    cache_ttl = 7200  # 2 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalize_base(input_value)
        findings: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # 1. Check for exposed API documentation
            async def probe_doc_path(path: str) -> dict[str, Any] | None:
                url = base_url + path
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "")
                        is_swagger = (
                            "swagger" in resp.text.lower()
                            or "openapi" in resp.text.lower()
                            or "application/json" in content_type
                        )
                        category = "graphql" if "graphql" in path else "swagger"
                        return {
                            "url": url,
                            "path": path,
                            "status_code": resp.status_code,
                            "finding_type": "Exposed API Documentation",
                            "owasp_category": _classify_owasp(path, category),
                            "is_swagger_openapi": is_swagger,
                            "risk": "High" if is_swagger else "Medium",
                        }
                except (httpx.RequestError, httpx.TimeoutException):
                    pass
                return None

            doc_tasks = [probe_doc_path(path) for path in _API_DOC_PATHS]
            doc_results = await asyncio.gather(*doc_tasks, return_exceptions=True)
            for result in doc_results:
                if isinstance(result, dict):
                    findings.append(result)

            # 2. Check for BOLA — compare responses for ID=1 vs ID=999
            bola_findings: list[dict[str, Any]] = []
            for path in _BOLA_PROBE_PATHS[:4]:
                url1 = base_url + path
                url_nonexist = url1.rsplit("/", 1)[0] + "/999999"
                try:
                    resp1, resp2 = await asyncio.gather(
                        client.get(url1),
                        client.get(url_nonexist),
                        return_exceptions=True,
                    )
                    if not isinstance(resp1, Exception) and not isinstance(resp2, Exception):
                        if resp1.status_code == 200 and resp2.status_code in (404, 400):
                            # ID 1 exists and is accessible; ID 999999 does not
                            content_type = resp1.headers.get("content-type", "")
                            has_mass_assignment = any(
                                kw in resp1.text.lower() for kw in _MASS_ASSIGNMENT_KEYWORDS
                            )
                            bola_findings.append({
                                "url": url1,
                                "path": path,
                                "finding_type": "Potential BOLA — Object Accessible Without Auth",
                                "owasp_category": _classify_owasp(path, "bola"),
                                "status_code": resp1.status_code,
                                "response_contains_sensitive_fields": has_mass_assignment,
                                "risk": "Critical" if has_mass_assignment else "High",
                            })
                            if has_mass_assignment:
                                bola_findings[-1]["mass_assignment_indicator"] = True
                                bola_findings[-1]["owasp_mass_assignment"] = _classify_owasp(path, "mass_assignment")
                except Exception:
                    pass
            findings.extend(bola_findings)

        total_findings = len(findings)
        severity_order = ["None", "Low", "Medium", "High", "Critical"]
        max_risk = "None"
        for f in findings:
            r = f.get("risk", "None")
            if severity_order.index(r) > severity_order.index(max_risk):
                max_risk = r

        return {
            "target": base_url,
            "found": total_findings > 0,
            "finding_count": total_findings,
            "findings": findings,
            "highest_risk": max_risk,
            "owasp_categories_found": list({f["owasp_category"] for f in findings}),
            "educational_note": (
                "The OWASP API Top 10 identifies the most critical API security risks. "
                "Exposed docs leak your attack surface; BOLA allows accessing other users' data "
                "by simply changing an ID in the URL — one of the most prevalent API flaws."
            ),
        }
