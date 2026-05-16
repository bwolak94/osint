"""GraphQL Security — introspection, batching DoS, and injection scanner.

Tests GraphQL endpoints for: introspection enabled (schema disclosure),
batch query abuse (N queries in one request), field suggestion enumeration,
depth limit bypass, alias bombing, and injection via GraphQL arguments.

Complements graphql_depth_auditor with broader attack surface coverage.
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

# Common GraphQL endpoint paths
_GRAPHQL_PATHS: list[str] = [
    "/graphql",
    "/graphql/v1",
    "/api/graphql",
    "/api/v1/graphql",
    "/v1/graphql",
    "/query",
    "/gql",
    "/graph",
]

# Introspection query
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

# Minimal introspection (type names only — sometimes allowed when full is blocked)
_MINI_INTROSPECTION = """
{
  __schema {
    types { name kind }
  }
}
"""

# Type suggestion probe — triggers "Did you mean" suggestion leak
_SUGGESTION_QUERY = """
{
  __typx {
    name
  }
}
"""

# Batch query (N identical queries in one request)
_BATCH_QUERY = [{"query": "{ __typename }"} for _ in range(50)]

# Alias bombing (one request, 100 aliases)
_alias_fields = "\n".join([f"f{i}: __typename" for i in range(100)])
_ALIAS_BOMB_QUERY = f"{{ {_alias_fields} }}"

# Fragment bombing
_FRAGMENT_BOMB_QUERY = """
query {
  ...F
}
fragment F on Query {
  __typename
  ...F2
}
fragment F2 on Query {
  __typename
  ...F3
}
fragment F3 on Query {
  __typename
}
"""

# SQLI via GraphQL argument
_SQLI_PROBE_QUERIES: list[tuple[str, str]] = [
    ('{ user(id: "1 OR 1=1") { id } }', "sqli_or"),
    ('{ user(id: "1\' OR \'1\'=\'1") { id } }', "sqli_quote"),
    ('{ search(query: "\' UNION SELECT 1,2,3--") { results } }', "sqli_union"),
]

# Sensitive type/field patterns in introspection
_SENSITIVE_SCHEMA_PATTERNS = re.compile(
    r'(?i)(password|secret|token|apiKey|api_key|internal|admin|'
    r'private|hidden|credit|ssn|dob|salary)',
)

# Error message patterns indicating GraphQL engine
_GRAPHQL_ENGINE_PATTERNS = re.compile(
    r'(?i)(graphql|syntax error|cannot query field|'
    r'field.*does not exist|did you mean|unknown type|'
    r'fragment.*on|__typename)',
)

# SQL error indicators via GraphQL args
_SQL_ERROR_PATTERNS = re.compile(
    r'(?i)(syntax error|sql|mysql|postgresql|sqlite|ora-\d+|'
    r'you have an error in your sql|unterminated|near ")")',
)


class GraphQLSecurityScanner(BaseOsintScanner):
    """GraphQL security vulnerability scanner.

    Detects introspection exposure, batch query abuse, alias bombing,
    field suggestion leaks, and injection vulnerabilities via GraphQL arguments.
    """

    scanner_name = "graphql_security"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        graphql_endpoints: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GQLScanner/1.0)",
                "Content-Type": "application/json",
            },
        ) as client:
            semaphore = asyncio.Semaphore(5)

            # Step 1: Discover GraphQL endpoints
            async def find_graphql(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # POST a minimal query
                        resp = await client.post(url, json={"query": "{ __typename }"})
                        if resp.status_code in (200, 400):
                            body = resp.text
                            if _GRAPHQL_ENGINE_PATTERNS.search(body) or "data" in body:
                                if url not in graphql_endpoints:
                                    graphql_endpoints.append(url)
                    except Exception:
                        pass

            await asyncio.gather(*[find_graphql(p) for p in _GRAPHQL_PATHS])

            if not graphql_endpoints:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "graphql_detected": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            for gql_url in graphql_endpoints[:3]:

                # Check 1: Introspection enabled
                try:
                    resp = await client.post(gql_url, json={"query": _INTROSPECTION_QUERY})
                    body = resp.text
                    if resp.status_code == 200 and "__schema" in body and "types" in body:
                        # Look for sensitive type/field names in schema
                        sensitive_match = _SENSITIVE_SCHEMA_PATTERNS.search(body)
                        vuln = {
                            "type": "graphql_introspection_enabled",
                            "severity": "medium",
                            "url": gql_url,
                            "description": "GraphQL introspection enabled — full schema disclosure",
                            "sensitive_types_found": sensitive_match.group(0) if sensitive_match else None,
                            "remediation": "Disable introspection in production (set introspection=False)",
                        }
                        vulnerabilities.append(vuln)
                        identifiers.append("vuln:graphql:introspection")

                        if sensitive_match:
                            vulnerabilities.append({
                                "type": "graphql_sensitive_schema",
                                "severity": "high",
                                "url": gql_url,
                                "evidence": sensitive_match.group(0),
                                "description": "Schema contains sensitive field names (password/token/admin)",
                            })
                            identifiers.append("vuln:graphql:sensitive_schema")

                except Exception:
                    pass

                # Check 2: Field suggestion leak (even when introspection disabled)
                try:
                    resp = await client.post(gql_url, json={"query": _SUGGESTION_QUERY})
                    body = resp.text
                    if "did you mean" in body.lower() or "suggestion" in body.lower():
                        # Extract suggested field names
                        suggestions = re.findall(r'[Dd]id you mean ["\'](\w+)["\']', body)
                        vulnerabilities.append({
                            "type": "graphql_field_suggestion_leak",
                            "severity": "low",
                            "url": gql_url,
                            "suggestions": suggestions[:10],
                            "description": "GraphQL field suggestion leaks type information (introspection partially disabled)",
                            "remediation": "Disable suggestions: NoSchemaIntrospectionCustomRule or disable_suggestions=True",
                        })
                        identifiers.append("vuln:graphql:suggestion_leak")
                except Exception:
                    pass

                # Check 3: Batch query abuse
                try:
                    resp = await client.post(gql_url, json=_BATCH_QUERY[:20])
                    if resp.status_code == 200:
                        body = resp.text
                        # Count how many responses came back
                        response_count = body.count('"data"')
                        if response_count >= 10:
                            vulnerabilities.append({
                                "type": "graphql_batch_query_enabled",
                                "severity": "medium",
                                "url": gql_url,
                                "requests_sent": 20,
                                "responses_received": response_count,
                                "description": "GraphQL batching enabled — potential DoS amplification",
                                "remediation": "Limit batch query count; implement query complexity analysis",
                            })
                            identifiers.append("vuln:graphql:batch_abuse")
                except Exception:
                    pass

                # Check 4: Alias bombing
                try:
                    resp = await client.post(gql_url, json={"query": _ALIAS_BOMB_QUERY})
                    if resp.status_code == 200:
                        body = resp.text
                        alias_count = body.count('"__typename"')
                        if alias_count > 50:
                            vulnerabilities.append({
                                "type": "graphql_alias_bombing",
                                "severity": "medium",
                                "url": gql_url,
                                "aliases_resolved": alias_count,
                                "description": "GraphQL alias bombing accepted — CPU/memory amplification possible",
                                "remediation": "Implement alias count limits and query depth/complexity limits",
                            })
                            identifiers.append("vuln:graphql:alias_bomb")
                except Exception:
                    pass

                # Check 5: SQL injection via GraphQL arguments
                for sqli_query, technique in _SQLI_PROBE_QUERIES:
                    try:
                        resp = await client.post(gql_url, json={"query": sqli_query})
                        body = resp.text
                        if _SQL_ERROR_PATTERNS.search(body):
                            match = _SQL_ERROR_PATTERNS.search(body)
                            vulnerabilities.append({
                                "type": "graphql_sqli",
                                "severity": "critical",
                                "url": gql_url,
                                "technique": technique,
                                "evidence": match.group(0)[:60] if match else "",
                                "description": "SQL injection via GraphQL argument — database error exposed",
                                "remediation": "Use parameterized resolvers; never interpolate GraphQL args into raw SQL",
                            })
                            ident = f"vuln:graphql:sqli:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
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
            "graphql_detected": True,
            "graphql_endpoints": graphql_endpoints,
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
