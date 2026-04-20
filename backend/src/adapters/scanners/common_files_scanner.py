"""Common files scanner — probes well-known paths for exposed sensitive files."""

import asyncio
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_PATHS: list[dict[str, Any]] = [
    {"path": "robots.txt", "sensitive": False},
    {"path": "security.txt", "sensitive": False},
    {"path": ".well-known/security.txt", "sensitive": False},
    {"path": "sitemap.xml", "sensitive": False},
    {"path": "humans.txt", "sensitive": False},
    {"path": "crossdomain.xml", "sensitive": True},
    {"path": "clientaccesspolicy.xml", "sensitive": True},
    {"path": ".env", "sensitive": True},
    {"path": ".git/config", "sensitive": True},
    {"path": "wp-login.php", "sensitive": True},
    {"path": "phpinfo.php", "sensitive": True},
]

_SNIPPET_LENGTH = 300


async def _probe_path(client: httpx.AsyncClient, base_url: str, entry: dict[str, Any]) -> dict[str, Any]:
    url = f"{base_url}/{entry['path']}"
    try:
        resp = await client.get(url)
        content_snippet = ""
        if resp.status_code == 200:
            try:
                content_snippet = resp.text[:_SNIPPET_LENGTH]
            except Exception:
                content_snippet = ""
        return {
            "path": entry["path"],
            "url": url,
            "status_code": resp.status_code,
            "content_snippet": content_snippet,
            "sensitive": entry["sensitive"],
            "accessible": resp.status_code == 200,
        }
    except Exception as exc:
        return {
            "path": entry["path"],
            "url": url,
            "status_code": None,
            "content_snippet": "",
            "sensitive": entry["sensitive"],
            "accessible": False,
            "error": str(exc),
        }


class CommonFilesScanner(BaseOsintScanner):
    """Probes well-known paths to detect exposed configuration and sensitive files."""

    scanner_name = "common_files"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if input_type == ScanInputType.URL:
            base_url = input_value.rstrip("/")
        else:
            base_url = f"https://{input_value}"

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        ) as client:
            tasks = [_probe_path(client, base_url, entry) for entry in _PATHS]
            results = await asyncio.gather(*tasks)

        accessible = [r for r in results if r["accessible"]]
        exposed_sensitive = [r for r in accessible if r["sensitive"]]

        return {
            "target": input_value,
            "found": len(accessible) > 0,
            "files": list(results),
            "accessible_count": len(accessible),
            "exposed_sensitive": exposed_sensitive,
            "extracted_identifiers": [],
        }
