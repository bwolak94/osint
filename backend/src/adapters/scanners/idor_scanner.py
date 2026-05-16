"""IDOR — Insecure Direct Object Reference vulnerability scanner.

Detects IDOR vulnerabilities by probing REST API endpoints with sequential,
predictable, and GUID-based object IDs. Analyzes response differences to
identify data leakage from unauthorized object access.

Tests: numeric IDs, GUIDs, username-based paths, and common object types
(users, orders, invoices, profiles, documents, files).
"""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common IDOR-prone API endpoint patterns
_IDOR_ENDPOINT_TEMPLATES: list[tuple[str, str]] = [
    # (path_template with {id} placeholder, resource_type)
    ("/api/v1/users/{id}", "user"),
    ("/api/v1/user/{id}", "user"),
    ("/api/users/{id}", "user"),
    ("/api/user/{id}", "user"),
    ("/api/v1/orders/{id}", "order"),
    ("/api/orders/{id}", "order"),
    ("/api/v1/invoices/{id}", "invoice"),
    ("/api/invoices/{id}", "invoice"),
    ("/api/v1/profiles/{id}", "profile"),
    ("/api/profiles/{id}", "profile"),
    ("/api/v1/documents/{id}", "document"),
    ("/api/documents/{id}", "document"),
    ("/api/v1/files/{id}", "file"),
    ("/api/files/{id}", "file"),
    ("/api/v1/accounts/{id}", "account"),
    ("/api/accounts/{id}", "account"),
    ("/api/v1/payments/{id}", "payment"),
    ("/api/payments/{id}", "payment"),
    ("/api/v1/tickets/{id}", "ticket"),
    ("/api/tickets/{id}", "ticket"),
    ("/api/v1/messages/{id}", "message"),
    ("/api/messages/{id}", "message"),
    ("/user/{id}/profile", "user_profile"),
    ("/user/{id}/settings", "user_settings"),
    ("/account/{id}", "account"),
    ("/profile/{id}", "profile"),
    ("/download/{id}", "download"),
    ("/export/{id}", "export"),
]

# Test IDs: start with low IDs most likely to exist
_TEST_IDS: list[str] = ["1", "2", "3", "0", "100", "1000", "-1"]

# GUIDs: nil + common test UUIDs
_TEST_GUIDS: list[str] = [
    "00000000-0000-0000-0000-000000000001",
    "00000000-0000-0000-0000-000000000002",
]

# Sensitive field patterns in response — indicates real data exposure
_SENSITIVE_DATA_PATTERNS = re.compile(
    r'(?i)"(email|password|phone|ssn|credit_card|card_number|dob|'
    r'date_of_birth|address|social|national_id|passport|bank_account|'
    r'secret|private_key|token|api_key|salary|balance)"',
)

# Common PII patterns
_PII_PATTERNS = re.compile(
    r'(?i)([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}|'  # email
    r'\+?[\d\s\-\(\)]{10,15}|'  # phone
    r'\b(?:\d{4}[- ]?){3}\d{4}\b)',  # credit card
)


class IDORScanner(BaseOsintScanner):
    """Insecure Direct Object Reference (IDOR) vulnerability scanner.

    Probes REST API endpoints with predictable IDs (sequential, GUIDs)
    and detects unauthorized data access by comparing response sizes
    and sensitive field presence.
    """

    scanner_name = "idor"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        accessible_endpoints: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; IDORScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(10)

            async def probe_endpoint(template: str, resource: str, obj_id: str) -> None:
                async with semaphore:
                    path = template.replace("{id}", obj_id)
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code in (200, 201):
                            body = resp.text
                            content_type = resp.headers.get("content-type", "")

                            # Check for sensitive data exposure
                            has_sensitive = bool(_SENSITIVE_DATA_PATTERNS.search(body))
                            has_pii = bool(_PII_PATTERNS.search(body))
                            is_json = "json" in content_type.lower()
                            body_size = len(body)

                            endpoint_info = {
                                "url": url,
                                "resource": resource,
                                "id_used": obj_id,
                                "status_code": resp.status_code,
                                "body_size": body_size,
                                "has_sensitive_fields": has_sensitive,
                                "has_pii": has_pii,
                                "is_json": is_json,
                            }
                            accessible_endpoints.append(endpoint_info)

                            if has_sensitive or has_pii:
                                # Extract a safe evidence snippet (first sensitive field name only)
                                evidence_match = _SENSITIVE_DATA_PATTERNS.search(body)
                                evidence = f"Field: {evidence_match.group(1)}" if evidence_match else "Sensitive data pattern found"

                                vulnerabilities.append({
                                    "type": "idor_sensitive_data_exposed",
                                    "severity": "high",
                                    "url": url,
                                    "resource": resource,
                                    "id_used": obj_id,
                                    "evidence": evidence,
                                    "has_pii": has_pii,
                                    "description": f"IDOR: {resource} endpoint at ID {obj_id} exposes sensitive fields without authentication",
                                    "remediation": "Implement object-level authorization; validate that the requesting user owns the resource",
                                })
                                ident = f"vuln:idor:{resource}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                            elif is_json and body_size > 50:
                                # JSON returned without auth — flag as potential IDOR even without PII
                                vulnerabilities.append({
                                    "type": "idor_unauthenticated_access",
                                    "severity": "medium",
                                    "url": url,
                                    "resource": resource,
                                    "id_used": obj_id,
                                    "body_size": body_size,
                                    "description": f"IDOR: {resource} endpoint returns JSON for ID {obj_id} without authentication check",
                                    "remediation": "Add authentication requirements and ownership verification",
                                })
                                ident = f"vuln:idor:unauth:{resource}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            # Test sequential numeric IDs
            tasks = []
            for template, resource in _IDOR_ENDPOINT_TEMPLATES[:14]:
                for obj_id in _TEST_IDS[:4]:
                    tasks.append(probe_endpoint(template, resource, obj_id))

            # Test GUIDs on a subset
            for template, resource in _IDOR_ENDPOINT_TEMPLATES[:6]:
                for guid in _TEST_GUIDS:
                    tasks.append(probe_endpoint(template, resource, guid))

            await asyncio.gather(*tasks)

            # Step 2: Enumerate ID range on discovered accessible endpoints
            # If ID=1 works, try 2,3,4,5 to confirm sequential enumeration
            confirmed_enumerable: list[str] = []
            if accessible_endpoints:
                seen_templates = set()
                for ep in accessible_endpoints[:3]:
                    # Extract template from URL
                    url = ep["url"]
                    resource = ep["resource"]
                    key = f"{resource}:{ep['id_used']}"
                    if resource in seen_templates:
                        continue
                    seen_templates.add(resource)

                    # Try next 3 IDs to confirm enumeration
                    current_id = ep["id_used"]
                    try:
                        next_id = str(int(current_id) + 1)
                        next_url = url.replace(f"/{current_id}", f"/{next_id}").replace(
                            f"/{current_id}/", f"/{next_id}/"
                        )
                        resp = await client.get(next_url)
                        if resp.status_code == 200 and len(resp.text) > 50:
                            confirmed_enumerable.append(url)
                            ident = f"vuln:idor:enumerable:{resource}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                                vulnerabilities.append({
                                    "type": "idor_enumerable_ids",
                                    "severity": "high",
                                    "resource": resource,
                                    "example_url": url,
                                    "next_url": next_url,
                                    "description": f"Sequential ID enumeration confirmed for {resource} — attackers can iterate all objects",
                                    "remediation": "Use unpredictable UUIDs as resource identifiers instead of sequential integers",
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
            "accessible_endpoints": len(accessible_endpoints),
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
