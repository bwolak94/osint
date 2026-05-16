"""Subdomain Permutation — alterx/dnsgen-style mutation and DNS resolution scanner.

Generates permutations of the target domain using common prefixes, suffixes,
separators, and number sequences (alterx patterns), then resolves them via
DNS to identify live subdomains missed by brute-force wordlists.

Mimics: alterx, dnsgen, gotator, ripgen Kali tools.
"""

from __future__ import annotations

import asyncio
import re
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common subdomain prefixes (from alterx default wordlists)
_PREFIXES: list[str] = [
    "dev", "staging", "stage", "prod", "production", "test", "qa", "uat",
    "api", "api2", "apiv2", "rest", "graphql", "grpc",
    "admin", "administrator", "panel", "dashboard", "control",
    "mail", "email", "smtp", "imap", "mx", "webmail",
    "vpn", "remote", "rdp", "citrix", "ssh", "bastion",
    "www", "web", "app", "apps", "portal",
    "cdn", "static", "assets", "media", "images", "img",
    "beta", "alpha", "demo", "sandbox",
    "internal", "intranet", "corp", "private",
    "git", "gitlab", "github", "bitbucket", "code", "repo",
    "jenkins", "ci", "cd", "build", "deploy",
    "monitor", "grafana", "kibana", "elastic", "logs",
    "db", "database", "mysql", "postgres", "redis", "mongo",
    "s3", "storage", "backup", "files", "upload",
    "auth", "login", "sso", "oauth", "id", "identity",
    "pay", "payment", "checkout", "billing", "invoice",
    "support", "help", "docs", "documentation", "wiki",
    "status", "health", "ping",
    "new", "old", "legacy", "v1", "v2", "v3",
    "us", "eu", "asia", "aws", "gcp", "azure",
    "shop", "store", "ecom",
    "mobile", "m", "wap",
    "secure", "ssl", "cert",
]

# Common suffixes to append to base domain name
_SUFFIXES: list[str] = [
    "-dev", "-staging", "-prod", "-test", "-qa",
    "-api", "-admin", "-portal", "-app",
    "-old", "-new", "-beta", "-alpha",
    "-v1", "-v2", "1", "2", "3",
    "-internal", "-corp",
    "-cdn", "-static",
]

# Number variants (dev1, dev2, staging01, etc.)
_NUMBER_VARIANTS: list[str] = ["1", "2", "3", "01", "02", "03", "001"]

# Cloudflare DoH for fast async resolution
_DOH_URL = "https://cloudflare-dns.com/dns-query"


class SubdomainPermutationScanner(BaseOsintScanner):
    """Subdomain permutation and resolution scanner (alterx/dnsgen style).

    Generates mutations of the target domain using prefix/suffix combinations,
    separators, and number variants, then resolves each via DNS-over-HTTPS
    to discover live subdomains not found in standard wordlists.
    """

    scanner_name = "subdomain_permutation"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        return await self._manual_scan(domain)

    async def _manual_scan(self, domain: str) -> dict[str, Any]:
        resolved: list[dict[str, Any]] = []
        identifiers: list[str] = []

        # Extract base name and TLD
        parts = domain.split(".")
        base = parts[0] if len(parts) >= 2 else domain
        tld = ".".join(parts[1:]) if len(parts) >= 2 else domain

        # Generate permutations
        candidates: set[str] = set()

        # prefix.base.tld
        for prefix in _PREFIXES:
            candidates.add(f"{prefix}.{domain}")

        # base-suffix.tld
        for suffix in _SUFFIXES:
            candidates.add(f"{base}{suffix}.{tld}")

        # prefix-base.tld and prefix.base-suffix.tld
        for prefix in _PREFIXES[:20]:
            candidates.add(f"{prefix}-{base}.{tld}")
            for suffix in _SUFFIXES[:5]:
                candidates.add(f"{prefix}.{base}{suffix}.{tld}")

        # Number variants: dev1.domain.com, staging01.domain.com
        for prefix in _PREFIXES[:15]:
            for num in _NUMBER_VARIANTS:
                candidates.add(f"{prefix}{num}.{domain}")
                candidates.add(f"{prefix}-{num}.{domain}")

        # Remove original domain from candidates
        candidates.discard(domain)

        semaphore = asyncio.Semaphore(30)  # High concurrency for DNS

        async with httpx.AsyncClient(
            timeout=5,
            verify=True,
            headers={"Accept": "application/dns-json"},
        ) as client:

            async def resolve_candidate(subdomain: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            _DOH_URL,
                            params={"name": subdomain, "type": "A"},
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            answers = data.get("Answer", [])
                            a_records = [a["data"] for a in answers if a.get("type") == 1]
                            if a_records:
                                resolved.append({
                                    "subdomain": subdomain,
                                    "ips": a_records[:4],
                                    "record_count": len(a_records),
                                })
                                identifiers.append(f"info:subdomain:{subdomain}")
                    except Exception:
                        pass

            # Resolve in parallel batches
            all_candidates = sorted(candidates)[:600]
            await asyncio.gather(*[resolve_candidate(c) for c in all_candidates])

        # Sort by subdomain name
        resolved.sort(key=lambda x: x["subdomain"])

        # Flag interesting findings
        interesting_keywords = {"admin", "internal", "dev", "staging", "api", "vpn", "ssh", "db", "database"}
        interesting_found = [
            r for r in resolved
            if any(kw in r["subdomain"].split(".")[0] for kw in interesting_keywords)
        ]

        return {
            "input": domain,
            "scan_mode": "manual_fallback",
            "permutations_generated": len(all_candidates),
            "live_subdomains": len(resolved),
            "resolved": resolved[:100],
            "interesting_subdomains": interesting_found[:20],
            "extracted_identifiers": identifiers[:50],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
