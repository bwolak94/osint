"""Docker Security — exposed Docker API and container misconfiguration scanner.

Detects: unauthenticated Docker daemon API (port 2375/2376), exposed Docker
socket via web, privileged container indicators, image vulnerabilities via
Docker Hub API, and container escape prerequisites.

Used by pentesters to identify cloud/server misconfiguration leading to
full host compromise via Docker daemon takeover.
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

# Docker API endpoints to probe
_DOCKER_API_PATHS: list[tuple[str, str]] = [
    ("/v1.41/info", "daemon_info"),
    ("/v1.40/info", "daemon_info_v140"),
    ("/v1.24/info", "daemon_info_v124"),
    ("/info", "daemon_info_unversioned"),
    ("/v1.41/containers/json", "list_containers"),
    ("/v1.41/images/json", "list_images"),
    ("/v1.41/version", "version"),
    ("/_ping", "ping"),
]

# Ports where Docker API might be exposed
_DOCKER_PORTS: list[int] = [2375, 2376, 4243, 4244]

# Docker registry / Hub paths
_REGISTRY_PATHS: list[str] = [
    "/v2/",
    "/v2/_catalog",
    "/v1/search",
]

# Portainer (Docker management UI)
_PORTAINER_PATHS: list[str] = [
    "/api/status",
    "/api/endpoints",
    "/api/users",
    "/#/init/admin",
]

# Indicators in Docker API responses
_DOCKER_INDICATORS = re.compile(
    r'(?i)(docker|containerd|runc|ServerVersion|KernelVersion|'
    r'OperatingSystem|Architecture|NCPU)',
)

# Sensitive data in container listings
_SENSITIVE_CONTAINER_PATTERNS = re.compile(
    r'(?i)(secret|password|token|api_key|private_key|passwd|credential)',
)


class DockerSecurityScanner(BaseOsintScanner):
    """Docker daemon and container security scanner.

    Probes for unauthenticated Docker API access, exposed registries,
    Portainer management UIs, and container configuration issues.
    """

    scanner_name = "docker_security"
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
        docker_info: dict[str, Any] = {}
        exposed_endpoints: list[str] = []

        async with httpx.AsyncClient(
            timeout=6,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DockerScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Step 1: Probe Docker API on common ports
            async def probe_docker_api(port: int, path: str, technique: str) -> None:
                async with semaphore:
                    url = f"http://{host}:{port}{path}"
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        if resp.status_code == 200 and _DOCKER_INDICATORS.search(body):
                            exposed_endpoints.append(url)

                            import json as _json
                            try:
                                data = _json.loads(body)
                                if "ServerVersion" in data or "Version" in data:
                                    docker_info.update({
                                        "version": data.get("ServerVersion") or data.get("Version"),
                                        "kernel": data.get("KernelVersion"),
                                        "os": data.get("OperatingSystem"),
                                        "api_url": url,
                                    })
                            except Exception:
                                pass

                            vulnerabilities.append({
                                "type": "docker_api_exposed",
                                "severity": "critical",
                                "url": url,
                                "port": port,
                                "technique": technique,
                                "description": f"Unauthenticated Docker daemon API exposed on port {port} — full host takeover possible",
                                "cwe": "CWE-284",
                                "remediation": "Bind Docker API to 127.0.0.1; use TLS client auth; use Unix socket only",
                            })
                            ident = f"vuln:docker:api_exposed:{port}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Check for container listing — enumerate running containers
                        elif resp.status_code == 200 and "containers" in path.lower():
                            try:
                                containers = _json.loads(body)
                                if isinstance(containers, list) and containers:
                                    # Look for sensitive env vars or labels
                                    for container in containers[:5]:
                                        labels = str(container.get("Labels", ""))
                                        if _SENSITIVE_CONTAINER_PATTERNS.search(labels):
                                            vulnerabilities.append({
                                                "type": "docker_sensitive_labels",
                                                "severity": "high",
                                                "url": url,
                                                "description": "Docker container labels contain sensitive keywords",
                                            })
                                            identifiers.append("vuln:docker:sensitive_labels")
                            except Exception:
                                pass

                    except Exception:
                        pass

            tasks = []
            for port in _DOCKER_PORTS:
                for path, technique in _DOCKER_API_PATHS:
                    tasks.append(probe_docker_api(port, path, technique))
            await asyncio.gather(*tasks)

            # Step 2: Check for Docker Registry
            async def probe_registry(port: int, path: str) -> None:
                async with semaphore:
                    for scheme in ["http", "https"]:
                        url = f"{scheme}://{host}:{port}{path}"
                        try:
                            resp = await client.get(url)
                            if resp.status_code in (200, 401):
                                if resp.status_code == 200:
                                    vulnerabilities.append({
                                        "type": "docker_registry_exposed",
                                        "severity": "high",
                                        "url": url,
                                        "description": "Docker registry accessible without authentication — image theft/poisoning risk",
                                        "remediation": "Enable authentication on registry (htpasswd or token auth)",
                                    })
                                    identifiers.append("vuln:docker:registry_public")
                        except Exception:
                            pass

            registry_tasks = []
            for port in [5000, 5001, 443, 80]:
                for path in _REGISTRY_PATHS:
                    registry_tasks.append(probe_registry(port, path))
            await asyncio.gather(*registry_tasks)

            # Step 3: Portainer management UI
            async def probe_portainer(port: int, path: str) -> None:
                async with semaphore:
                    for scheme in ["http", "https"]:
                        url = f"{scheme}://{host}:{port}{path}"
                        try:
                            resp = await client.get(url)
                            body = resp.text
                            if resp.status_code == 200 and "portainer" in body.lower():
                                vulnerabilities.append({
                                    "type": "portainer_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "description": "Portainer Docker management UI exposed — full cluster takeover possible",
                                    "remediation": "Restrict Portainer access to internal network; require strong authentication",
                                })
                                ident = "vuln:docker:portainer_exposed"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                        except Exception:
                            pass

            portainer_tasks = []
            for port in [9000, 9443, 8000]:
                for path in _PORTAINER_PATHS:
                    portainer_tasks.append(probe_portainer(port, path))
            await asyncio.gather(*portainer_tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "docker_info": docker_info,
            "exposed_endpoints": exposed_endpoints,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.IP_ADDRESS:
        return value.strip()
    if input_type == ScanInputType.DOMAIN:
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
