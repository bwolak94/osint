"""Container Escape Auditor — checks for exposed Docker and Kubernetes APIs.

Module 115 in the Infrastructure & Exploitation domain. Probes the target host for
unauthenticated Docker daemon API exposure (ports 2375/2376) and Kubernetes API server
exposure (ports 6443, 8080). An exposed Docker API grants root-equivalent control over
the host; an exposed kube-apiserver with anonymous access is equally critical.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_DOCKER_PORTS = [2375, 2376]
_KUBE_PORTS = [6443, 8080, 8443]
_ETCD_PORTS = [2379, 2380]

_DOCKER_API_PATHS = ["/version", "/info", "/containers/json", "/_ping"]
_KUBE_API_PATHS = ["/version", "/api", "/api/v1/namespaces", "/api/v1/pods", "/healthz"]


def _extract_host(input_value: str) -> str:
    value = input_value.strip()
    value = value.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    return value


async def _tcp_port_open(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if a TCP port is open."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False


async def _probe_docker_api(client: httpx.AsyncClient, host: str, port: int) -> dict[str, Any] | None:
    """Probe Docker API on the given port."""
    scheme = "https" if port == 2376 else "http"
    base_url = f"{scheme}://{host}:{port}"

    for path in _DOCKER_API_PATHS:
        url = base_url + path
        try:
            resp = await client.get(url, timeout=8)
            if resp.status_code in (200, 401, 403):
                is_docker = "Server" in resp.headers and "docker" in resp.headers.get("Server", "").lower()
                try:
                    data = resp.json()
                except Exception:
                    data = {}

                authenticated_required = resp.status_code in (401, 403)
                return {
                    "type": "Docker API",
                    "host": host,
                    "port": port,
                    "path": path,
                    "url": url,
                    "status_code": resp.status_code,
                    "unauthenticated_access": not authenticated_required and resp.status_code == 200,
                    "docker_version": data.get("Version") or data.get("ApiVersion", ""),
                    "containers_accessible": path == "/containers/json" and resp.status_code == 200,
                    "risk": "Critical" if not authenticated_required and resp.status_code == 200 else "High",
                }
        except (httpx.RequestError, httpx.TimeoutException):
            continue
    return None


async def _probe_kube_api(client: httpx.AsyncClient, host: str, port: int) -> dict[str, Any] | None:
    """Probe Kubernetes API server on the given port."""
    scheme = "https" if port in (6443, 8443) else "http"
    base_url = f"{scheme}://{host}:{port}"

    for path in _KUBE_API_PATHS:
        url = base_url + path
        try:
            resp = await client.get(url, timeout=8, verify=False)
            if resp.status_code in (200, 401, 403):
                try:
                    data = resp.json()
                except Exception:
                    data = {}

                is_kube = (
                    "major" in data and "minor" in data  # /version response
                    or "apiVersion" in data
                    or "kubernetes" in resp.text.lower()
                )
                if not is_kube:
                    continue

                anonymous_access = resp.status_code == 200
                return {
                    "type": "Kubernetes API",
                    "host": host,
                    "port": port,
                    "path": path,
                    "url": url,
                    "status_code": resp.status_code,
                    "anonymous_access": anonymous_access,
                    "kube_version": f"{data.get('major', '')}.{data.get('minor', '')}".strip("."),
                    "risk": "Critical" if anonymous_access else "High",
                }
        except (httpx.RequestError, httpx.TimeoutException, Exception):
            continue
    return None


class ContainerEscapeAuditorScanner(BaseOsintScanner):
    """Checks for exposed Docker daemon and Kubernetes API server endpoints.

    Probes TCP ports 2375/2376 (Docker) and 6443/8080/8443 (Kubernetes) on the
    target host and attempts to interact with the respective APIs. An exposed
    unauthenticated Docker API grants full container and host control (Module 115).
    """

    scanner_name = "container_escape_auditor"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.IP_ADDRESS})
    cache_ttl = 3600  # 1 hour

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = _extract_host(input_value)
        findings: list[dict[str, Any]] = []

        # First check which ports are open
        port_checks: list[tuple[str, int]] = [
            ("docker", p) for p in _DOCKER_PORTS
        ] + [
            ("kube", p) for p in _KUBE_PORTS
        ]

        open_ports: list[int] = []
        port_tasks = [_tcp_port_open(host, port) for _, port in port_checks]
        port_results = await asyncio.gather(*port_tasks, return_exceptions=True)

        for (service_type, port), is_open in zip(port_checks, port_results):
            if is_open is True:
                open_ports.append(port)

        if not open_ports:
            return {
                "target": host,
                "found": False,
                "open_ports": [],
                "findings": [],
                "severity": "None",
                "educational_note": "No Docker or Kubernetes API ports are open on this target.",
            }

        # Probe open ports
        async with httpx.AsyncClient(
            timeout=10,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            probe_tasks = []
            for port in open_ports:
                if port in _DOCKER_PORTS:
                    probe_tasks.append(_probe_docker_api(client, host, port))
                elif port in _KUBE_PORTS:
                    probe_tasks.append(_probe_kube_api(client, host, port))

            probe_results = await asyncio.gather(*probe_tasks, return_exceptions=True)
            for result in probe_results:
                if isinstance(result, dict):
                    findings.append(result)

        critical = any(f.get("risk") == "Critical" for f in findings)
        severity = "Critical" if critical else ("High" if findings else "None")

        return {
            "target": host,
            "found": len(findings) > 0,
            "open_ports": open_ports,
            "findings": findings,
            "severity": severity,
            "risk_assessment": {
                "docker_api_exposed": any(f["type"] == "Docker API" and f.get("unauthenticated_access") for f in findings),
                "kubernetes_api_exposed": any(f["type"] == "Kubernetes API" and f.get("anonymous_access") for f in findings),
            },
            "educational_note": (
                "An exposed Docker API (port 2375) without TLS or authentication grants "
                "full root access to the host. Kubernetes API servers should never allow "
                "anonymous access. Container escapes via these vectors are trivial to exploit."
            ),
            "recommendations": [
                "Never expose Docker daemon socket without TLS client certificates.",
                "Bind Docker API to localhost or a Unix socket only.",
                "Enable Kubernetes RBAC and disable anonymous authentication.",
                "Use network policies and firewalls to restrict API server access.",
                "Audit container runtime with tools like kube-bench (CIS benchmarks).",
            ],
        }
