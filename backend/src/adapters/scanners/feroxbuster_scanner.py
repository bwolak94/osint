"""Feroxbuster — fast, recursive content discovery / directory fuzzing.

Discovers hidden files, directories, and API endpoints via wordlist-based
enumeration. Kali Linux staple for web application reconnaissance.

Two-mode operation:
1. **feroxbuster binary** — if on PATH, invoked for full recursive scan
2. **Manual fallback** — HTTP probing with a curated common-path wordlist
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Curated wordlist covering most-common web paths
_COMMON_PATHS: list[tuple[str, str]] = [
    # Admin / management panels
    ("/admin", "admin_panel"),
    ("/admin/", "admin_panel"),
    ("/administrator", "admin_panel"),
    ("/wp-admin", "wordpress_admin"),
    ("/login", "login_page"),
    ("/dashboard", "dashboard"),
    ("/panel", "panel"),
    ("/cpanel", "cpanel"),
    ("/management", "management"),
    ("/manager", "manager"),
    ("/console", "console"),
    # API endpoints
    ("/api", "api_endpoint"),
    ("/api/v1", "api_v1"),
    ("/api/v2", "api_v2"),
    ("/api/v3", "api_v3"),
    ("/rest", "rest_api"),
    ("/graphql", "graphql"),
    ("/swagger", "swagger"),
    ("/swagger-ui", "swagger"),
    ("/api-docs", "api_docs"),
    ("/openapi.json", "openapi_spec"),
    ("/openapi.yaml", "openapi_spec"),
    # Config / backup files
    ("/.env", "env_file"),
    ("/.env.bak", "env_backup"),
    ("/config.php", "config_file"),
    ("/config.yaml", "config_file"),
    ("/config.json", "config_file"),
    ("/settings.py", "settings_file"),
    ("/web.config", "web_config"),
    ("/app.config", "app_config"),
    ("/database.yml", "database_config"),
    # Source / version control
    ("/.git", "git_exposed"),
    ("/.git/config", "git_config"),
    ("/.svn", "svn_exposed"),
    ("/.hg", "mercurial_exposed"),
    # Backup files
    ("/backup", "backup_dir"),
    ("/backups", "backup_dir"),
    ("/backup.zip", "backup_archive"),
    ("/backup.tar.gz", "backup_archive"),
    ("/site.tar.gz", "backup_archive"),
    ("/dump.sql", "database_dump"),
    # Common dev/debug paths
    ("/phpinfo.php", "phpinfo"),
    ("/info.php", "phpinfo"),
    ("/test.php", "test_file"),
    ("/debug", "debug_endpoint"),
    ("/health", "health_check"),
    ("/status", "status_page"),
    ("/ping", "ping_endpoint"),
    ("/metrics", "metrics"),
    ("/actuator", "spring_actuator"),
    ("/actuator/health", "spring_health"),
    ("/actuator/env", "spring_env_exposed"),
    ("/actuator/heapdump", "spring_heapdump"),
    # Uploads / media
    ("/uploads", "uploads_dir"),
    ("/upload", "upload_endpoint"),
    ("/files", "files_dir"),
    ("/static", "static_dir"),
    ("/assets", "assets_dir"),
    ("/images", "images_dir"),
    ("/media", "media_dir"),
    # Logs
    ("/logs", "logs_dir"),
    ("/log", "logs_dir"),
    ("/error_log", "error_log"),
    ("/access_log", "access_log"),
    # Robots / sitemaps
    ("/robots.txt", "robots_txt"),
    ("/sitemap.xml", "sitemap"),
    ("/sitemap_index.xml", "sitemap"),
    # Framework-specific
    ("/vendor", "vendor_dir"),
    ("/node_modules", "node_modules"),
    ("/composer.json", "composer_config"),
    ("/package.json", "package_json"),
    ("/requirements.txt", "requirements"),
    ("/Gemfile", "gemfile"),
    # Auth / reset
    ("/register", "register_page"),
    ("/signup", "signup_page"),
    ("/reset-password", "password_reset"),
    ("/forgot-password", "password_reset"),
    ("/logout", "logout_endpoint"),
    # Users / data
    ("/users", "users_endpoint"),
    ("/user", "users_endpoint"),
    ("/profile", "profile_page"),
    ("/account", "account_page"),
    ("/search", "search_endpoint"),
]

_INTERESTING_STATUS = {200, 201, 204, 301, 302, 307, 308, 401, 403}


class FeroxbusterScanner(BaseOsintScanner):
    """Recursive content discovery / directory fuzzing scanner.

    Enumerates hidden paths, admin panels, API endpoints, backup files,
    and framework-specific locations on the target web application.
    """

    scanner_name = "feroxbuster"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 180

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("feroxbuster"):
            return await self._run_feroxbuster_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_feroxbuster_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"feroxbuster_{run_id}.json")
        cmd = [
            "feroxbuster",
            "--url", base_url,
            "--output", out_file,
            "--json",
            "--no-recursion",
            "--silent",
            "--timeout", "10",
            "--threads", "25",
            "--depth", "2",
            "--status-codes", "200,201,204,301,302,307,308,401,403",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 20)
        except asyncio.TimeoutError:
            log.warning("feroxbuster timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        discovered: list[dict[str, Any]] = []
        identifiers: list[str] = []

        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("type") == "response":
                                url = entry.get("url", "")
                                status = entry.get("status", 0)
                                length = entry.get("content_length", 0)
                                discovered.append({
                                    "url": url,
                                    "status_code": status,
                                    "content_length": length,
                                })
                                identifiers.append(f"url:{url}")
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception as exc:
                log.warning("Failed to parse feroxbuster output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        return {
            "input": input_value,
            "scan_mode": "feroxbuster_binary",
            "base_url": base_url,
            "discovered_paths": discovered,
            "total_found": len(discovered),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        discovered: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Feroxbuster/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(15)

            async def probe(path: str, finding_id: str) -> None:
                target = base_url.rstrip("/") + path
                async with semaphore:
                    try:
                        resp = await client.get(target)
                        if resp.status_code in _INTERESTING_STATUS:
                            entry = {
                                "url": target,
                                "path": path,
                                "status_code": resp.status_code,
                                "content_length": len(resp.content),
                                "finding_id": finding_id,
                            }
                            discovered.append(entry)
                            identifiers.append(f"url:{target}")
                    except Exception:
                        pass

            tasks = [probe(path, fid) for path, fid in _COMMON_PATHS]
            await asyncio.gather(*tasks)

        # Sort by status code then path
        discovered.sort(key=lambda x: (x["status_code"], x["path"]))

        # Severity hints
        high_interest = {200, 201}
        findings_summary = {
            "accessible": [d for d in discovered if d["status_code"] in high_interest],
            "redirects": [d for d in discovered if d["status_code"] in {301, 302, 307, 308}],
            "forbidden": [d for d in discovered if d["status_code"] == 403],
            "unauthorized": [d for d in discovered if d["status_code"] == 401],
        }

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "discovered_paths": discovered,
            "total_found": len(discovered),
            "findings_summary": {k: len(v) for k, v in findings_summary.items()},
            "high_interest_paths": [d["path"] for d in findings_summary["accessible"]],
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value.rstrip("/")
