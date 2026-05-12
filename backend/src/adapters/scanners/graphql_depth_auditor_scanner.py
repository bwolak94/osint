"""GraphQL Depth Auditor — audits GraphQL endpoints for security misconfigurations.

Module 122 in the Infrastructure & Exploitation domain. Probes the target URL for
GraphQL endpoints, checks whether introspection is enabled (leaking the full schema),
tests for missing query depth limits (allows deeply nested queries), and checks for
absence of query complexity limits. These are common GraphQL-specific security issues.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_GRAPHQL_PATHS = ["/graphql", "/api/graphql", "/v1/graphql", "/gql", "/query"]

_INTROSPECTION_QUERY = """
{
  __schema {
    queryType { name }
    mutationType { name }
    types {
      name
      kind
      fields { name }
    }
  }
}
"""

# A deeply-nested query to test for depth limit enforcement
_DEPTH_PROBE_QUERY = """
{
  __type(name: "Query") {
    fields {
      type {
        fields {
          type {
            fields {
              type {
                fields {
                  name
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

_BATCH_QUERY = """
[
  { "query": "{ __typename }" },
  { "query": "{ __typename }" },
  { "query": "{ __typename }" },
  { "query": "{ __typename }" },
  { "query": "{ __typename }" }
]
"""


def _normalize_base(input_value: str) -> str:
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _probe_graphql_endpoint(client: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
    """Check if URL responds to a basic GraphQL introspection request."""
    try:
        resp = await client.post(
            url,
            json={"query": "{ __typename }"},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (200, 400) and "application/json" in resp.headers.get("content-type", ""):
            data = resp.json()
            # Any JSON response to a GraphQL query strongly suggests GraphQL
            if "data" in data or "errors" in data:
                return {"url": url, "status_code": resp.status_code, "response": data}
    except (httpx.RequestError, json.JSONDecodeError, httpx.TimeoutException):
        pass
    return None


class GraphQLDepthAuditorScanner(BaseOsintScanner):
    """Audits GraphQL endpoints for introspection exposure and missing depth/complexity limits.

    Discovers GraphQL endpoints on the target, then tests for introspection enabled,
    deeply-nested query acceptance (no depth limit), and query batching support.
    Returns the schema exposure level and security posture assessment (Module 122).
    """

    scanner_name = "graphql_depth_auditor"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 7200  # 2 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = input_value.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
        base = _normalize_base(target)

        findings: list[dict[str, Any]] = []
        discovered_endpoints: list[str] = []

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # 1. Discover GraphQL endpoints
            for path in _GRAPHQL_PATHS:
                endpoint_url = base + path
                result = await _probe_graphql_endpoint(client, endpoint_url)
                if result:
                    discovered_endpoints.append(endpoint_url)

            # If input is a full URL ending with a GraphQL path, also test it directly
            if any(path in target for path in _GRAPHQL_PATHS) and target not in discovered_endpoints:
                result = await _probe_graphql_endpoint(client, target)
                if result:
                    discovered_endpoints.append(target)

            for endpoint in discovered_endpoints[:3]:
                endpoint_findings: dict[str, Any] = {
                    "endpoint": endpoint,
                    "introspection_enabled": False,
                    "depth_limit_enforced": True,
                    "batching_enabled": False,
                    "schema_types": [],
                    "schema_query_fields": [],
                }

                # 2. Test full introspection
                try:
                    resp = await client.post(
                        endpoint,
                        json={"query": _INTROSPECTION_QUERY},
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        schema = data.get("data", {}).get("__schema", {})
                        if schema:
                            endpoint_findings["introspection_enabled"] = True
                            types = schema.get("types", [])
                            endpoint_findings["schema_types"] = [t["name"] for t in types if not t["name"].startswith("__")][:30]
                            findings.append({
                                "finding": "Introspection Enabled",
                                "endpoint": endpoint,
                                "risk": "High",
                                "detail": f"Full schema exposed with {len(types)} types.",
                                "owasp": "API9:2023 - Improper Inventory Management",
                            })
                except (httpx.RequestError, json.JSONDecodeError):
                    pass

                # 3. Test depth limit
                try:
                    resp = await client.post(
                        endpoint,
                        json={"query": _DEPTH_PROBE_QUERY},
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if "errors" not in data or not any(
                            "depth" in str(e).lower() or "complexity" in str(e).lower()
                            for e in data.get("errors", [])
                        ):
                            endpoint_findings["depth_limit_enforced"] = False
                            findings.append({
                                "finding": "No Query Depth Limit",
                                "endpoint": endpoint,
                                "risk": "Medium",
                                "detail": "Deeply nested queries accepted without error — DoS risk.",
                                "owasp": "API4:2023 - Unrestricted Resource Consumption",
                            })
                except (httpx.RequestError, json.JSONDecodeError):
                    pass

                # 4. Test query batching
                try:
                    resp = await client.post(
                        endpoint,
                        content=_BATCH_QUERY,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 1:
                            endpoint_findings["batching_enabled"] = True
                            findings.append({
                                "finding": "Query Batching Enabled",
                                "endpoint": endpoint,
                                "risk": "Medium",
                                "detail": "Multiple queries can be batched in a single request — rate limiting bypass risk.",
                                "owasp": "API4:2023 - Unrestricted Resource Consumption",
                            })
                except (httpx.RequestError, json.JSONDecodeError):
                    pass

        max_risk = "None"
        severity_order = ["None", "Low", "Medium", "High", "Critical"]
        for f in findings:
            r = f.get("risk", "None")
            if severity_order.index(r) > severity_order.index(max_risk):
                max_risk = r

        return {
            "target": target,
            "found": len(discovered_endpoints) > 0,
            "endpoints_discovered": discovered_endpoints,
            "finding_count": len(findings),
            "findings": findings,
            "highest_risk": max_risk,
            "educational_note": (
                "GraphQL introspection in production reveals the complete API schema to attackers. "
                "Missing depth/complexity limits enable denial-of-service via expensive nested queries. "
                "Disable introspection in production and implement query cost analysis."
            ),
        }
