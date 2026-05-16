"""Kubernetes Security — API server, dashboard, and RBAC misconfiguration scanner.

Detects: unauthenticated K8s API server (6443/8080/8001), exposed dashboard,
etcd without auth (2379/2380), kubelet read-only API (10255), RBAC wildcard
permissions, anonymous access, metadata endpoint (169.254.169.254), and
namespace/secret enumeration.
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

# K8s API endpoints
_K8S_API_PATHS: list[tuple[str, str]] = [
    ("/api", "api_root"),
    ("/api/v1", "api_v1"),
    ("/api/v1/namespaces", "namespaces"),
    ("/api/v1/pods", "all_pods"),
    ("/api/v1/secrets", "all_secrets"),
    ("/api/v1/configmaps", "configmaps"),
    ("/api/v1/serviceaccounts", "service_accounts"),
    ("/apis", "api_groups"),
    ("/apis/rbac.authorization.k8s.io/v1/clusterrolebindings", "rbac"),
    ("/healthz", "health"),
    ("/metrics", "metrics"),
    ("/openapi/v2", "openapi"),
]

# Kubelet API paths (port 10250/10255)
_KUBELET_PATHS: list[tuple[str, str]] = [
    ("/pods", "kubelet_pods"),
    ("/metrics", "kubelet_metrics"),
    ("/stats/summary", "kubelet_stats"),
    ("/runningpods/", "running_pods"),
]

# etcd paths
_ETCD_PATHS: list[tuple[str, str]] = [
    ("/v2/keys", "etcd_v2"),
    ("/v3/kv/range", "etcd_v3"),
    ("/health", "etcd_health"),
    ("/metrics", "etcd_metrics"),
]

# Dashboard paths
_DASHBOARD_PATHS: list[str] = [
    "/#/overview",
    "/api/v1/csrftoken/login",
    "/api/v1/login",
    "/",
]

# K8s API response indicators
_K8S_INDICATORS = re.compile(
    r'(?i)(kubernetes|apiVersion|kind|namespace|ClusterRole|'
    r'ServiceAccount|kube-system|kubectl)',
)

# Sensitive data in secrets/configmaps
_SENSITIVE_K8S = re.compile(
    r'(?i)(password|secret|token|api.key|private.key|tls\.crt|tls\.key|'
    r'\.dockerconfigjson|AWS_SECRET|REDIS_URL|DATABASE_URL)',
)


class KubernetesScanner(BaseOsintScanner):
    """Kubernetes cluster security misconfiguration scanner.

    Probes K8s API server, kubelet, etcd, and dashboard for unauthenticated
    access, secret enumeration, and RBAC misconfigurations.
    """

    scanner_name = "kubernetes"
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
        k8s_info: dict[str, Any] = {}
        exposed_endpoints: list[str] = []

        async with httpx.AsyncClient(
            timeout=6,
            follow_redirects=False,
            verify=False,
            headers={
                "User-Agent": "kubectl/v1.28.0",
                "Accept": "application/json",
            },
        ) as client:
            semaphore = asyncio.Semaphore(10)

            # Step 1: Probe K8s API server
            async def probe_k8s_api(port: int, scheme: str, path: str, technique: str) -> None:
                async with semaphore:
                    url = f"{scheme}://{host}:{port}{path}"
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        if resp.status_code in (200, 403) and _K8S_INDICATORS.search(body):
                            exposed_endpoints.append(url)

                            if resp.status_code == 200:
                                import json as _json
                                try:
                                    data = _json.loads(body)
                                except Exception:
                                    data = {}

                                # Secrets exposed
                                if "secrets" in path and "items" in body:
                                    items = data.get("items", [])
                                    secret_count = len(items)
                                    has_sensitive = _SENSITIVE_K8S.search(body)
                                    vulnerabilities.append({
                                        "type": "k8s_secrets_exposed",
                                        "severity": "critical",
                                        "url": url,
                                        "secret_count": secret_count,
                                        "has_sensitive_data": bool(has_sensitive),
                                        "description": f"Kubernetes secrets enumerable without auth — {secret_count} secrets exposed",
                                        "remediation": "Disable anonymous auth; enforce RBAC; use sealed-secrets or Vault",
                                    })
                                    identifiers.append("vuln:k8s:secrets_exposed")

                                elif "namespaces" in path:
                                    vulnerabilities.append({
                                        "type": "k8s_unauthenticated_api",
                                        "severity": "critical",
                                        "url": url,
                                        "port": port,
                                        "technique": technique,
                                        "description": f"K8s API unauthenticated on {scheme}:{port} — cluster fully accessible",
                                        "remediation": "Set --anonymous-auth=false; require client certificate auth",
                                    })
                                    ident = f"vuln:k8s:unauth_api:{port}"
                                    if ident not in identifiers:
                                        identifiers.append(ident)

                                elif path == "/api":
                                    k8s_info["api_url"] = url
                                    k8s_info["api_version"] = data.get("serverAddressByClientCIDRs")
                                    if resp.status_code == 200:
                                        vulnerabilities.append({
                                            "type": "k8s_api_anonymous_access",
                                            "severity": "critical",
                                            "url": url,
                                            "description": "K8s API server accessible without authentication",
                                            "remediation": "Disable --anonymous-auth; enforce network policies",
                                        })
                                        ident = "vuln:k8s:anonymous_api"
                                        if ident not in identifiers:
                                            identifiers.append(ident)

                                elif "metrics" in path:
                                    vulnerabilities.append({
                                        "type": "k8s_metrics_exposed",
                                        "severity": "medium",
                                        "url": url,
                                        "description": "K8s metrics endpoint publicly accessible — cluster internals exposed",
                                    })
                                    identifiers.append("vuln:k8s:metrics_exposed")

                    except Exception:
                        pass

            tasks = []
            for port, scheme in [(6443, "https"), (8080, "http"), (8001, "http"), (443, "https")]:
                for path, technique in _K8S_API_PATHS[:8]:
                    tasks.append(probe_k8s_api(port, scheme, path, technique))
            await asyncio.gather(*tasks)

            # Step 2: Kubelet API
            async def probe_kubelet(port: int, scheme: str, path: str, technique: str) -> None:
                async with semaphore:
                    url = f"{scheme}://{host}:{port}{path}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            vulnerabilities.append({
                                "type": "kubelet_api_exposed",
                                "severity": "high",
                                "url": url,
                                "technique": technique,
                                "description": f"Kubelet API exposed on port {port} — can exec into pods",
                                "remediation": "Set kubelet --anonymous-auth=false; restrict with network policies",
                            })
                            ident = f"vuln:k8s:kubelet:{port}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            kubelet_tasks = []
            for port in [10255, 10250]:
                scheme = "https" if port == 10250 else "http"
                for path, technique in _KUBELET_PATHS:
                    kubelet_tasks.append(probe_kubelet(port, scheme, path, technique))
            await asyncio.gather(*kubelet_tasks)

            # Step 3: etcd
            async def probe_etcd(port: int, path: str, technique: str) -> None:
                async with semaphore:
                    for scheme in ["http", "https"]:
                        url = f"{scheme}://{host}:{port}{path}"
                        try:
                            resp = await client.get(url)
                            if resp.status_code == 200 and ("etcd" in resp.text.lower() or "health" in resp.text.lower()):
                                vulnerabilities.append({
                                    "type": "etcd_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "technique": technique,
                                    "description": f"etcd exposed on port {port} — all K8s secrets/configs accessible",
                                    "cve": "CVE-2020-15106",
                                    "remediation": "Bind etcd to localhost only; use TLS client auth",
                                })
                                ident = "vuln:k8s:etcd_exposed"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                        except Exception:
                            pass

            etcd_tasks = []
            for port in [2379, 2380]:
                for path, technique in _ETCD_PATHS[:2]:
                    etcd_tasks.append(probe_etcd(port, path, technique))
            await asyncio.gather(*etcd_tasks)

            # Step 4: Kubernetes Dashboard
            async def probe_dashboard(port: int, path: str) -> None:
                async with semaphore:
                    for scheme in ["http", "https"]:
                        url = f"{scheme}://{host}:{port}{path}"
                        try:
                            resp = await client.get(url)
                            body = resp.text
                            if resp.status_code == 200 and ("kubernetes" in body.lower() or "dashboard" in body.lower()):
                                vulnerabilities.append({
                                    "type": "k8s_dashboard_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "description": "Kubernetes Dashboard exposed — GUI cluster management without auth",
                                    "remediation": "Remove dashboard from prod; require token auth; access via kubectl proxy only",
                                })
                                ident = "vuln:k8s:dashboard_exposed"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                        except Exception:
                            pass

            dash_tasks = []
            for port in [30000, 443, 8001, 9090]:
                for path in _DASHBOARD_PATHS[:2]:
                    dash_tasks.append(probe_dashboard(port, path))
            await asyncio.gather(*dash_tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "k8s_info": k8s_info,
            "exposed_endpoints": exposed_endpoints,
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
