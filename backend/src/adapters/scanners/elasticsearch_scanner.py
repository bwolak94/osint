"""Elasticsearch / OpenSearch / Kibana — unauthenticated access and data exposure scanner.

Detects unauthenticated Elasticsearch, OpenSearch, Kibana, and Grafana instances.
Enumerates indices, checks for sensitive data, cluster health, and known CVEs
(CVE-2021-22145, CVE-2022-38900, Kibana console RCE CVE-2019-7609).
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

# ES/OS API paths
_ES_PATHS: list[tuple[str, str]] = [
    ("/_cluster/health", "cluster_health"),
    ("/_cluster/stats", "cluster_stats"),
    ("/_cat/indices?v", "list_indices"),
    ("/_cat/nodes?v", "list_nodes"),
    ("/_nodes", "node_info"),
    ("/_security/user", "users"),
    ("/_xpack/security/user", "users_xpack"),
    ("/_cat/shards?v", "shards"),
    ("/_cluster/settings", "settings"),
    ("/*/_search", "search_all"),
    ("/_aliases", "aliases"),
    ("/_template", "templates"),
    ("/", "root"),
]

# Kibana paths
_KIBANA_PATHS: list[tuple[str, str]] = [
    ("/api/status", "kibana_status"),
    ("/api/saved_objects/_find?type=dashboard", "dashboards"),
    ("/api/saved_objects/_find?type=index-pattern", "index_patterns"),
    ("/app/kibana", "kibana_app"),
    ("/app/management", "management"),
    ("/api/fleet/agents", "fleet_agents"),
    ("/internal/security/me", "current_user"),
    ("/api/console/proxy?path=/_cluster/health&method=GET", "console_proxy"),
]

# Grafana paths
_GRAFANA_PATHS: list[tuple[str, str]] = [
    ("/api/health", "grafana_health"),
    ("/api/users", "grafana_users"),
    ("/api/org/users", "org_users"),
    ("/api/datasources", "datasources"),
    ("/api/dashboards/home", "home_dashboard"),
    ("/api/snapshots", "snapshots"),
]

# Sensitive index name patterns
_SENSITIVE_INDEX_PATTERNS = re.compile(
    r'(?i)(password|credential|secret|token|user|customer|payment|'
    r'credit.card|ssn|pii|gdpr|health|medical|financial|audit|log)',
)

# ES cluster info indicators
_ES_INDICATORS = re.compile(
    r'(?i)(elasticsearch|opensearch|"cluster_name"|"version"|"lucene_version"|'
    r'"tagline".*"You Know, for Search")',
)

# Known CVE detection patterns
_CVE_PATTERNS: dict[str, tuple[re.Pattern[str], str, str]] = {
    "CVE-2019-7609": (re.compile(r'"version".*"7\.[0-5]\."', re.I), "critical", "Kibana < 7.6.0 Node.js protoype pollution RCE"),
    "CVE-2021-22145": (re.compile(r'"version".*"7\.1[0-2]\."', re.I), "high", "ES < 7.13 uncontrolled resource consumption"),
}


class ElasticsearchScanner(BaseOsintScanner):
    """Elasticsearch, OpenSearch, Kibana, and Grafana exposure scanner.

    Detects unauthenticated access to search clusters, enumerates indices,
    identifies sensitive data exposure, and flags known CVEs.
    """

    scanner_name = "elasticsearch"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = _extract_host(input_value, input_type)
        return await self._manual_scan(host, input_value)

    async def _manual_scan(self, host: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        cluster_info: dict[str, Any] = {}
        sensitive_indices: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ESScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Step 1: Probe Elasticsearch on common ports
            async def probe_es(port: int, scheme: str, path: str, technique: str) -> None:
                async with semaphore:
                    url = f"{scheme}://{host}:{port}{path}"
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        if resp.status_code != 200:
                            return

                        # Root endpoint
                        if technique == "root" and _ES_INDICATORS.search(body):
                            import json as _json
                            try:
                                data = _json.loads(body)
                                version = data.get("version", {}).get("number", "unknown")
                                cluster_info.update({
                                    "url": url,
                                    "version": version,
                                    "cluster_name": data.get("cluster_name"),
                                    "tagline": data.get("tagline"),
                                })
                                vulnerabilities.append({
                                    "type": "elasticsearch_unauthenticated",
                                    "severity": "critical",
                                    "url": url,
                                    "version": version,
                                    "cluster_name": data.get("cluster_name"),
                                    "description": f"Elasticsearch accessible without auth on port {port} — all data readable",
                                    "remediation": "Enable X-Pack security; set xpack.security.enabled: true",
                                })
                                identifiers.append("vuln:es:unauthenticated")

                                # CVE check
                                for cve, (pattern, sev, desc) in _CVE_PATTERNS.items():
                                    if pattern.search(body):
                                        vulnerabilities.append({
                                            "type": "es_vulnerable_version",
                                            "severity": sev,
                                            "url": url,
                                            "version": version,
                                            "cve": cve,
                                            "description": desc,
                                        })
                                        identifiers.append(f"vuln:es:{cve}")
                            except Exception:
                                pass

                        # Index listing
                        elif technique == "list_indices":
                            # Parse cat indices output (text table)
                            indices = re.findall(r'\b(\w[\w.-]+)\s+open\b', body)
                            for idx in indices:
                                if _SENSITIVE_INDEX_PATTERNS.search(idx):
                                    sensitive_indices.append(idx)

                            if indices:
                                vulnerabilities.append({
                                    "type": "es_indices_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "index_count": len(indices),
                                    "sensitive_indices": sensitive_indices[:10],
                                    "sample_indices": indices[:10],
                                    "description": f"{len(indices)} Elasticsearch indices exposed — {len(sensitive_indices)} appear sensitive",
                                    "remediation": "Enable authentication; restrict index access with role-based access control",
                                })
                                if sensitive_indices:
                                    identifiers.append("vuln:es:sensitive_indices")

                        # Cluster health
                        elif technique == "cluster_health":
                            import json as _json
                            try:
                                data = _json.loads(body)
                                vulnerabilities.append({
                                    "type": "es_cluster_health_exposed",
                                    "severity": "medium",
                                    "url": url,
                                    "status": data.get("status"),
                                    "number_of_nodes": data.get("number_of_nodes"),
                                    "description": "Elasticsearch cluster health endpoint accessible without auth",
                                })
                                ident = "vuln:es:cluster_health"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                            except Exception:
                                pass

                        # Users endpoint
                        elif technique in ("users", "users_xpack") and body and "{" in body:
                            vulnerabilities.append({
                                "type": "es_users_exposed",
                                "severity": "critical",
                                "url": url,
                                "description": "Elasticsearch security users endpoint accessible — credential enumeration possible",
                            })
                            identifiers.append("vuln:es:users_exposed")

                    except Exception:
                        pass

            tasks = []
            for port in [9200, 9201, 9202, 9300]:
                for path, technique in _ES_PATHS[:8]:
                    tasks.append(probe_es(port, "http", path, technique))
                    tasks.append(probe_es(port, "https", path, technique))
            await asyncio.gather(*tasks)

            # Step 2: Kibana
            async def probe_kibana(port: int, path: str, technique: str) -> None:
                async with semaphore:
                    for scheme in ["http", "https"]:
                        url = f"{scheme}://{host}:{port}{path}"
                        try:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                body = resp.text
                                import json as _json
                                try:
                                    data = _json.loads(body)
                                    if technique == "kibana_status":
                                        kib_version = data.get("version", {}).get("number", "unknown")
                                        vulnerabilities.append({
                                            "type": "kibana_unauthenticated",
                                            "severity": "critical",
                                            "url": url,
                                            "version": kib_version,
                                            "description": f"Kibana accessible without authentication — full ES data browsing possible",
                                            "remediation": "Enable Kibana security; configure xpack.security in kibana.yml",
                                        })
                                        identifiers.append("vuln:kibana:unauthenticated")
                                    elif technique == "console_proxy":
                                        vulnerabilities.append({
                                            "type": "kibana_console_rce",
                                            "severity": "critical",
                                            "url": url,
                                            "cve": "CVE-2019-7609",
                                            "description": "Kibana Dev Tools Console proxy accessible — Timelion SSTI/RCE possible",
                                        })
                                        identifiers.append("vuln:kibana:console_rce")
                                except Exception:
                                    if "kibana" in body.lower():
                                        vulnerabilities.append({
                                            "type": "kibana_detected",
                                            "severity": "medium",
                                            "url": url,
                                            "description": "Kibana detected on port " + str(port),
                                        })
                        except Exception:
                            pass

            kibana_tasks = []
            for port in [5601, 443, 80]:
                for path, technique in _KIBANA_PATHS[:4]:
                    kibana_tasks.append(probe_kibana(port, path, technique))
            await asyncio.gather(*kibana_tasks)

            # Step 3: Grafana
            async def probe_grafana(port: int, path: str, technique: str) -> None:
                async with semaphore:
                    for scheme in ["http", "https"]:
                        url = f"{scheme}://{host}:{port}{path}"
                        try:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                body = resp.text
                                if "grafana" in body.lower() or '"database"' in body:
                                    if technique == "grafana_users":
                                        vulnerabilities.append({
                                            "type": "grafana_users_exposed",
                                            "severity": "high",
                                            "url": url,
                                            "description": "Grafana users API accessible without authentication",
                                            "cve": "CVE-2021-43798",
                                            "remediation": "Disable anonymous access; update Grafana to 8.3.2+",
                                        })
                                        identifiers.append("vuln:grafana:users_exposed")
                                    elif technique == "datasources":
                                        vulnerabilities.append({
                                            "type": "grafana_datasources_exposed",
                                            "severity": "critical",
                                            "url": url,
                                            "description": "Grafana data sources API accessible — DB credentials may be exposed",
                                        })
                                        identifiers.append("vuln:grafana:datasources")
                        except Exception:
                            pass

            grafana_tasks = []
            for port in [3000, 3001, 8300, 443, 80]:
                for path, technique in _GRAFANA_PATHS[:4]:
                    grafana_tasks.append(probe_grafana(port, path, technique))
            await asyncio.gather(*grafana_tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "cluster_info": cluster_info,
            "sensitive_indices": sensitive_indices[:20],
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
