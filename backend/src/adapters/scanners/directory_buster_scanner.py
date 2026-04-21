"""Directory Buster — checks target for common exposed paths and sensitive endpoints.

Module 85 in the Infrastructure & Exploitation domain. Probes a curated list of
commonly misconfigured or forgotten paths (.git, /admin, /swagger, /.env, etc.)
on the user-supplied target. Returns discovered paths with their HTTP status codes
to help identify unintended exposure.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_COMMON_PATHS: list[str] = [
    "/.git/HEAD",
    "/.git/config",
    "/.env",
    "/.env.local",
    "/.env.production",
    "/admin",
    "/admin/login",
    "/administrator",
    "/wp-admin",
    "/wp-login.php",
    "/wp-config.php",
    "/config.php",
    "/config.yml",
    "/config.json",
    "/configuration.php",
    "/phpinfo.php",
    "/info.php",
    "/server-status",
    "/server-info",
    "/backup",
    "/backup.zip",
    "/backup.tar.gz",
    "/db.sql",
    "/dump.sql",
    "/database.sql",
    "/api/docs",
    "/api/v1/docs",
    "/swagger",
    "/swagger.json",
    "/swagger.yaml",
    "/openapi.json",
    "/openapi.yaml",
    "/docs",
    "/.htaccess",
    "/.htpasswd",
    "/robots.txt",
    "/sitemap.xml",
    "/crossdomain.xml",
    "/clientaccesspolicy.xml",
    "/.DS_Store",
    "/Thumbs.db",
    "/web.config",
    "/dockerfile",
    "/docker-compose.yml",
    "/Makefile",
    "/package.json",
    "/composer.json",
    "/requirements.txt",
    "/Gemfile",
    "/debug",
    "/console",
    "/trace",
    "/actuator",
    "/actuator/env",
    "/actuator/health",
    "/metrics",
    "/health",
    "/_profiler",
    "/phpmyadmin",
    "/adminer.php",
    "/elmah.axd",
    "/elmah",
]

_INTERESTING_STATUSES = {200, 201, 301, 302, 401, 403}


def _normalize_base(input_value: str) -> str:
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _probe_path(client: httpx.AsyncClient, base: str, path: str) -> dict[str, Any] | None:
    url = base.rstrip("/") + path
    try:
        resp = await client.get(url, follow_redirects=False)
        if resp.status_code in _INTERESTING_STATUSES:
            return {
                "path": path,
                "url": url,
                "status_code": resp.status_code,
                "content_length": int(resp.headers.get("content-length", len(resp.content))),
                "content_type": resp.headers.get("content-type", "").split(";")[0].strip(),
                "interesting": resp.status_code == 200,
            }
    except (httpx.RequestError, httpx.TimeoutException):
        pass
    return None


class DirectoryBusterScanner(BaseOsintScanner):
    """Probes common exposed paths on the target server.

    Checks a curated wordlist of sensitive/misconfigured paths and returns
    those that respond with noteworthy HTTP status codes. Only targets the
    domain/URL supplied by the user (Module 85).
    """

    scanner_name = "directory_buster"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200  # 2 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalize_base(input_value)

        found_paths: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # Probe in batches of 10 to avoid overwhelming the target
            batch_size = 10
            for i in range(0, len(_COMMON_PATHS), batch_size):
                batch = _COMMON_PATHS[i : i + batch_size]
                tasks = [_probe_path(client, base_url, path) for path in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, dict):
                        found_paths.append(result)

        accessible = [p for p in found_paths if p["status_code"] == 200]
        sensitive = [p for p in accessible if any(
            keyword in p["path"]
            for keyword in [".git", ".env", "config", "backup", "sql", "phpinfo", "admin", "swagger", "openapi", "actuator"]
        )]

        return {
            "target": base_url,
            "found": len(found_paths) > 0,
            "total_probed": len(_COMMON_PATHS),
            "interesting_count": len(found_paths),
            "accessible_count": len(accessible),
            "sensitive_exposures": sensitive,
            "found_paths": found_paths,
            "severity": "Critical" if sensitive else ("Medium" if accessible else "Low"),
            "recommendations": [
                "Remove or password-protect administrative endpoints.",
                "Ensure .git directories are not accessible from the web root.",
                "Remove backup files and SQL dumps from public directories.",
                "Disable directory listing in web server configuration.",
                "Place sensitive config files outside the web root.",
            ],
        }
