"""Dangling DNS Scanner — detects CNAME records pointing to decommissioned services.

Module 125 in the Infrastructure & Exploitation domain. Resolves CNAME chains for
the target domain and its common subdomains, then checks whether the ultimate
canonical target is still active. Identifies records pointing to cloud service
patterns (GitHub Pages, Heroku, Netlify, Vercel, Azure, etc.) that return
indicators of unclaimed or deleted resources — a classic subdomain takeover vector.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common subdomains to check for dangling CNAMEs
_PROBE_SUBDOMAINS = [
    "",  # apex
    "www",
    "blog",
    "mail",
    "shop",
    "app",
    "api",
    "dev",
    "staging",
    "beta",
    "help",
    "docs",
    "support",
    "status",
    "cdn",
    "assets",
    "static",
]

# Cloud service CNAME patterns and their "resource not found" response signatures
_CLOUD_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "GitHub Pages",
        "pattern": ".github.io",
        "error_signatures": ["There isn't a GitHub Pages site here", "404 Not Found"],
    },
    {
        "name": "Heroku",
        "pattern": ".herokuapp.com",
        "error_signatures": ["No such app", "herokucdn.com/error-pages/no-such-app"],
    },
    {
        "name": "Netlify",
        "pattern": ".netlify.app",
        "error_signatures": ["Not found - Request ID", "netlify.com/"],
    },
    {
        "name": "Vercel",
        "pattern": ".vercel.app",
        "error_signatures": ["The deployment could not be found", "404: NOT_FOUND"],
    },
    {
        "name": "Azure Web Apps",
        "pattern": ".azurewebsites.net",
        "error_signatures": ["Microsoft Azure App Service", "404 Web Site not found"],
    },
    {
        "name": "Amazon S3",
        "pattern": ".s3.amazonaws.com",
        "error_signatures": ["NoSuchBucket", "The specified bucket does not exist"],
    },
    {
        "name": "Fastly",
        "pattern": ".fastly.net",
        "error_signatures": ["Fastly error: unknown domain"],
    },
    {
        "name": "Ghost",
        "pattern": ".ghost.io",
        "error_signatures": ["404 - There is no site with that address"],
    },
    {
        "name": "Shopify",
        "pattern": ".myshopify.com",
        "error_signatures": ["Sorry, this shop is currently unavailable"],
    },
    {
        "name": "Tumblr",
        "pattern": ".tumblr.com",
        "error_signatures": ["There's nothing here"],
    },
]


def _get_cname(hostname: str) -> str | None:
    """Resolve a CNAME record for the hostname using getaddrinfo heuristic."""
    try:
        import dns.resolver  # type: ignore[import-untyped]
        answers = dns.resolver.resolve(hostname, "CNAME")
        return str(answers[0].target).rstrip(".")
    except Exception:
        pass
    # Fallback: socket cannot give CNAME directly — return None
    return None


def _detect_cloud_pattern(cname: str) -> dict[str, Any] | None:
    """Match a CNAME against known cloud service patterns."""
    cname_lower = cname.lower()
    for cloud in _CLOUD_PATTERNS:
        if cloud["pattern"] in cname_lower:
            return cloud
    return None


async def _check_dangling(
    client: httpx.AsyncClient,
    subdomain: str,
    base_domain: str,
) -> dict[str, Any] | None:
    """Check a single subdomain for a dangling CNAME."""
    hostname = f"{subdomain}.{base_domain}" if subdomain else base_domain

    cname = _get_cname(hostname)
    if cname is None:
        return None

    cloud = _detect_cloud_pattern(cname)
    if cloud is None:
        return None

    # Probe the subdomain HTTP response for error signatures
    url = f"https://{hostname}"
    is_dangling = False
    error_found = ""
    status_code: int | None = None

    try:
        resp = await client.get(url, follow_redirects=True)
        status_code = resp.status_code
        body = resp.text
        for sig in cloud["error_signatures"]:
            if sig.lower() in body.lower():
                is_dangling = True
                error_found = sig
                break
    except (httpx.RequestError, httpx.TimeoutException):
        # Connection failure can also indicate dangling resource
        is_dangling = True
        error_found = "Connection failed — target hostname may not exist"

    if is_dangling:
        return {
            "subdomain": hostname,
            "cname": cname,
            "cloud_provider": cloud["name"],
            "error_signature": error_found,
            "status_code": status_code,
            "takeover_potential": "High",
            "takeover_method": f"Claim the resource at {cloud['name']} using the CNAME value.",
        }
    return None


class DanglingDNSScanner(BaseOsintScanner):
    """Detects CNAME records pointing to decommissioned cloud services.

    Probes common subdomains of the target domain for CNAMEs that resolve to
    cloud provider patterns (GitHub Pages, Heroku, Netlify, etc.) but return
    'resource not found' indicators, signalling subdomain takeover opportunity
    (Module 125).
    """

    scanner_name = "dangling_dns"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_domain = input_value.strip().lower().lstrip("www.").split("/")[0]

        dangling_records: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            tasks = [_check_dangling(client, sub, base_domain) for sub in _PROBE_SUBDOMAINS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict):
                    dangling_records.append(result)

        return {
            "target": base_domain,
            "found": len(dangling_records) > 0,
            "subdomains_checked": len(_PROBE_SUBDOMAINS),
            "dangling_count": len(dangling_records),
            "dangling_records": dangling_records,
            "severity": "High" if dangling_records else "None",
            "educational_note": (
                "Subdomain takeover exploits dangling DNS records — CNAMEs that still point "
                "to cloud services whose resources have been deleted. An attacker can claim "
                "the orphaned resource and serve malicious content under the victim's domain."
            ),
            "recommendations": [
                "Audit DNS records when decommissioning services and remove dangling CNAMEs.",
                "Implement DNS monitoring to alert on new CNAME additions.",
                "Use cloud provider subdomain takeover prevention features where available.",
            ],
        }
