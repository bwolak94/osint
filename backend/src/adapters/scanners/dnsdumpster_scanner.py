"""DNSDumpster scanner — passive DNS recon via dnsdumpster.com HTML scraping."""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://dnsdumpster.com"


class DNSDumpsterScanner(BaseOsintScanner):
    """Scrapes dnsdumpster.com for passive DNS data including subdomains, MX, NS, and TXT records.

    No API key required. Uses a CSRF token extracted from the initial GET response cookie jar.
    Uses httpx for async HTTP (not the requests library).
    """

    scanner_name = "dnsdumpster"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Referer": _BASE_URL,
            },
        ) as client:
            try:
                return await self._scrape(client, input_value)
            except Exception as e:
                log.error("DNSDumpster scan failed", domain=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

    async def _scrape(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        # Step 1: GET the homepage to obtain the CSRF token from the cookie jar
        get_resp = await client.get(_BASE_URL + "/")
        get_resp.raise_for_status()

        csrf_token = client.cookies.get("csrftoken", "")
        if not csrf_token:
            # Fallback: try to extract from hidden form input in HTML
            match = re.search(r'csrfmiddlewaretoken["\s]+value=["\']([\w]+)', get_resp.text)
            if match:
                csrf_token = match.group(1)

        if not csrf_token:
            log.warning("DNSDumpster: could not obtain CSRF token", domain=domain)
            return {
                "input": domain,
                "found": False,
                "error": "Could not obtain CSRF token from dnsdumpster.com",
                "extracted_identifiers": [],
            }

        # Step 2: POST the domain search
        post_resp = await client.post(
            _BASE_URL + "/",
            data={
                "csrfmiddlewaretoken": csrf_token,
                "targetip": domain,
                "user": "free",
            },
            headers={
                "Origin": _BASE_URL,
                "Referer": _BASE_URL + "/",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        post_resp.raise_for_status()
        html = post_resp.text

        subdomains: list[dict[str, str]] = []
        host_records: list[dict[str, str]] = []
        dns_records: dict[str, list[str]] = {
            "A": [],
            "MX": [],
            "NS": [],
            "TXT": [],
        }
        identifiers: list[str] = []

        # Parse DNS tables — dnsdumpster renders results in HTML tables
        # Pattern: table rows with subdomain, IP, reverse DNS, and ASN info
        table_pattern = re.compile(
            r"<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]*)</td>",
            re.IGNORECASE | re.DOTALL,
        )

        # Extract A-record / host rows
        host_table_match = re.search(
            r"<h4[^>]*>A Records.*?</h4>(.*?)</table>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if host_table_match:
            rows = re.findall(
                r"<td[^>]*>([\w.\-]+\." + re.escape(domain) + r")</td>\s*<td[^>]*>([\d.]+)</td>",
                host_table_match.group(1),
                re.IGNORECASE,
            )
            for subdomain, ip in rows:
                host_records.append({"subdomain": subdomain, "ip": ip})
                subdomains.append({"subdomain": subdomain, "ip": ip})
                identifiers.append(f"domain:{subdomain}")
                identifiers.append(f"ip:{ip}")
                if ip not in dns_records["A"]:
                    dns_records["A"].append(ip)

        # Extract MX records
        mx_match = re.search(
            r"<h4[^>]*>MX Records.*?</h4>(.*?)</table>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if mx_match:
            for mx in re.findall(r"<td[^>]*>([\w.\-]+)</td>", mx_match.group(1)):
                mx = mx.strip()
                if mx and mx not in dns_records["MX"]:
                    dns_records["MX"].append(mx)
                    identifiers.append(f"domain:{mx}")

        # Extract NS records
        ns_match = re.search(
            r"<h4[^>]*>NS Records.*?</h4>(.*?)</table>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if ns_match:
            for ns in re.findall(r"<td[^>]*>([\w.\-]+)</td>", ns_match.group(1)):
                ns = ns.strip()
                if ns and ns not in dns_records["NS"]:
                    dns_records["NS"].append(ns)

        # Extract TXT records
        txt_match = re.search(
            r"<h4[^>]*>TXT Records.*?</h4>(.*?)</table>",
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if txt_match:
            for txt in re.findall(r"<td[^>]*>([^<]+)</td>", txt_match.group(1)):
                txt = txt.strip()
                if txt:
                    dns_records["TXT"].append(txt)

        # Deduplicate identifiers
        identifiers = list(dict.fromkeys(identifiers))

        return {
            "input": domain,
            "found": bool(subdomains or any(dns_records.values())),
            "subdomains": subdomains,
            "host_records": host_records,
            "dns_records": dns_records,
            "subdomain_count": len(subdomains),
            "extracted_identifiers": identifiers,
        }
