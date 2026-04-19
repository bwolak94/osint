"""Enhanced Wayback Machine CDX Server API scanner."""

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

# Patterns that indicate interesting/sensitive URLs
_INTERESTING_PATTERNS = re.compile(
    r"(admin|api|login|backup|\.git|\.env|config|password|\.sql|\.bak|"
    r"secret|token|key|credential|private|internal|staging|debug|console|"
    r"phpinfo|wp-admin|wp-login|setup|install)",
    re.IGNORECASE,
)


class WaybackCdxScanner(BaseOsintScanner):
    scanner_name = "wayback_cdx"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = _normalise_domain(input_value)

        async with httpx.AsyncClient(timeout=20) as client:
            main_task = asyncio.create_task(_fetch_main_cdx(client, domain))
            subdomain_task = asyncio.create_task(_fetch_subdomain_cdx(client, domain))

            main_rows, subdomain_rows = await asyncio.gather(
                main_task, subdomain_task, return_exceptions=True
            )

        if isinstance(main_rows, BaseException):
            log.warning("main CDX fetch failed", error=str(main_rows))
            main_rows = []
        if isinstance(subdomain_rows, BaseException):
            log.warning("subdomain CDX fetch failed", error=str(subdomain_rows))
            subdomain_rows = []

        return _build_result(input_value, domain, main_rows, subdomain_rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_domain(value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        return parsed.netloc or value
    return value


async def _fetch_main_cdx(client: httpx.AsyncClient, domain: str) -> list[list[str]]:
    """Fetch URLs under domain/* from CDX API."""
    resp = await client.get(
        "http://web.archive.org/cdx/search/cdx",
        params={
            "url": f"{domain}/*",
            "output": "json",
            "fl": "original,statuscode,timestamp,mimetype",
            "collapse": "urlkey",
            "limit": "500",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if not data or len(data) < 2:
        return []
    return data[1:]  # skip header row


async def _fetch_subdomain_cdx(client: httpx.AsyncClient, domain: str) -> list[list[str]]:
    """Fetch all subdomains ever seen in Wayback."""
    resp = await client.get(
        "http://web.archive.org/cdx/search/cdx",
        params={
            "url": f"*.{domain}",
            "output": "json",
            "fl": "original",
            "collapse": "urlkey",
            "limit": "200",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if not data or len(data) < 2:
        return []
    return data[1:]


def _build_result(
    input_value: str,
    domain: str,
    main_rows: list[list[str]],
    subdomain_rows: list[list[str]],
) -> dict[str, Any]:
    unique_urls: list[str] = []
    interesting_urls: list[str] = []
    content_types: dict[str, int] = {}
    status_breakdown: dict[str, int] = {}
    timestamps: list[str] = []

    seen_urls: set[str] = set()

    for row in main_rows:
        if len(row) < 4:
            continue
        url, status, timestamp, mimetype = row[0], row[1], row[2], row[3]

        if url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append(url)

        if status:
            status_breakdown[status] = status_breakdown.get(status, 0) + 1

        if mimetype:
            content_types[mimetype] = content_types.get(mimetype, 0) + 1

        if timestamp:
            timestamps.append(timestamp)

        if _INTERESTING_PATTERNS.search(url):
            interesting_urls.append(url)

    # Subdomains from CDX
    subdomains_found: list[str] = []
    for row in subdomain_rows:
        if not row:
            continue
        url = row[0]
        host = _extract_host(url)
        if host and host != domain and host.endswith(f".{domain}"):
            subdomains_found.append(host)

    subdomains_found = list(dict.fromkeys(subdomains_found))
    interesting_urls = list(dict.fromkeys(interesting_urls))

    first_seen = min(timestamps) if timestamps else None
    last_seen = max(timestamps) if timestamps else None

    identifiers: list[str] = [f"domain:{sub}" for sub in subdomains_found]
    identifiers += [f"url:{url}" for url in interesting_urls]

    return {
        "input": input_value,
        "found": bool(unique_urls or subdomains_found),
        "total_snapshots": len(main_rows),
        "unique_urls": len(unique_urls),
        "interesting_urls": interesting_urls,
        "subdomains_found": subdomains_found,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "content_types": content_types,
        "status_breakdown": status_breakdown,
        "extracted_identifiers": list(dict.fromkeys(identifiers)),
    }


def _extract_host(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.split(":")[0]
    except Exception:
        return ""
