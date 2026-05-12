"""Subdomain takeover scanner — detects dangling CNAME records pointing at unclaimed services."""

import socket
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Fingerprints: (provider_name, cname_contains_or_response_contains, response_body_fingerprint)
_TAKEOVER_FINGERPRINTS: list[dict[str, str]] = [
    {"provider": "GitHub Pages", "cname": "github.io", "body": "There isn't a GitHub Pages site here"},
    {"provider": "Heroku", "cname": "herokuapp.com", "body": "no-such-app.herokuapp.com"},
    {"provider": "Fastly", "cname": "fastly.net", "body": "Fastly error: unknown domain"},
    {"provider": "Netlify", "cname": "netlify.app", "body": "Not Found"},
    {"provider": "AWS S3", "cname": "s3.amazonaws.com", "body": "NoSuchBucket"},
    {"provider": "AWS S3 (region)", "cname": ".s3-website", "body": "NoSuchBucket"},
    {"provider": "Azure", "cname": "azurewebsites.net", "body": "404 Web Site not found"},
    {"provider": "Shopify", "cname": "myshopify.com", "body": "Sorry, this shop is currently unavailable"},
    {"provider": "Tumblr", "cname": "domains.tumblr.com", "body": "Whatever you were looking for doesn't currently exist"},
    {"provider": "Squarespace", "cname": "squarespace.com", "body": "No Such Account"},
    {"provider": "WP Engine", "cname": "wpengine.com", "body": "The site you were looking for couldn't be found"},
    {"provider": "Ghost", "cname": "ghost.io", "body": "The thing you were looking for is no longer here"},
    {"provider": "Surge", "cname": "surge.sh", "body": "project not found"},
    {"provider": "Pantheon", "cname": "pantheon.io", "body": "404 error unknown site"},
    {"provider": "Zendesk", "cname": "zendesk.com", "body": "Help Center Closed"},
]

_COMMON_SUBDOMAINS = [
    "www", "mail", "ftp", "vpn", "api", "dev", "staging", "test",
    "blog", "shop", "store", "cdn", "static", "assets", "app",
]


def _resolve_cname(hostname: str) -> str | None:
    try:
        import dns.resolver
        answers = dns.resolver.resolve(hostname, "CNAME")
        return str(answers[0].target).rstrip(".")
    except Exception:
        return None


async def _check_takeover(subdomain: str) -> dict[str, Any] | None:
    cname = _resolve_cname(subdomain)
    if not cname:
        return None

    matched_provider: str | None = None
    matched_fingerprint: str | None = None

    for fp in _TAKEOVER_FINGERPRINTS:
        if fp["cname"] in cname:
            matched_provider = fp["provider"]
            matched_fingerprint = fp["body"]
            break

    if not matched_provider:
        return None

    # Check the HTTP response for the fingerprint
    takeover_possible = False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            resp = await client.get(f"http://{subdomain}")
            if matched_fingerprint and matched_fingerprint.lower() in resp.text.lower():
                takeover_possible = True
    except Exception:
        pass

    return {
        "subdomain": subdomain,
        "cname": cname,
        "provider": matched_provider,
        "takeover_possible": takeover_possible,
        "fingerprint": matched_fingerprint,
    }


class SubdomainTakeoverScanner(BaseOsintScanner):
    """Detects subdomain takeover vulnerabilities via dangling CNAME records."""

    scanner_name = "subdomain_takeover"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 7200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        import asyncio

        subdomains_to_check = [input_value] + [f"{sub}.{input_value}" for sub in _COMMON_SUBDOMAINS]

        semaphore = asyncio.Semaphore(10)

        async def guarded(sub: str) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    return await _check_takeover(sub)
                except Exception:
                    return None

        results = await asyncio.gather(*[guarded(sub) for sub in subdomains_to_check])
        findings = [r for r in results if r is not None]
        vulnerable = [f for f in findings if f["takeover_possible"]]

        return {
            "domain": input_value,
            "found": len(vulnerable) > 0,
            "vulnerable_subdomains": vulnerable,
            "all_cname_findings": findings,
            "subdomains_checked": len(subdomains_to_check),
            "extracted_identifiers": [f"domain:{f['subdomain']}" for f in findings],
        }
