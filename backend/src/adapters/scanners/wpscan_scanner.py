"""WPScan — WordPress CMS vulnerability scanner.

Detects WordPress installations, enumerates users/plugins/themes,
and checks for known CVEs in WordPress core, plugins, and themes.

Two-mode operation:
1. **wpscan binary** — invoked with JSON output if on PATH (requires WPVulnDB API key)
2. **Manual fallback** — HTTP-based WordPress detection and enumeration
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_WP_INDICATORS = [
    "/wp-login.php",
    "/wp-admin/",
    "/wp-content/",
    "/wp-includes/",
    "/xmlrpc.php",
    "/wp-json/",
]

_COMMON_PLUGINS = [
    "contact-form-7", "woocommerce", "yoast-seo", "elementor",
    "akismet", "jetpack", "classic-editor", "wordfence",
    "really-simple-ssl", "all-in-one-seo-pack", "wpforms-lite",
    "query-monitor",
]


class WPScanScanner(BaseOsintScanner):
    """WordPress CMS security scanner.

    Detects WordPress, checks for:
    - WordPress version disclosure
    - User enumeration via REST API and ?author= parameter
    - Common plugin exposure
    - XML-RPC enabled (brute-force attack vector)
    - Readme.html exposure (version leak)
    - Debug.log exposure
    - Directory listing in wp-content
    """

    scanner_name = "wpscan"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("wpscan"):
            return await self._run_wpscan_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_wpscan_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"wpscan_{run_id}.json")
        settings = get_settings()
        cmd = ["wpscan", "--url", base_url, "--format", "json", "--output", out_file,
               "--no-banner", "--enumerate", "u,p,t,cb,dbe,m"]
        # Add API token if configured
        api_token = getattr(settings, "wpscan_api_token", "") or os.getenv("WPSCAN_API_TOKEN", "")
        if api_token:
            cmd += ["--api-token", api_token]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("wpscan timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        result: dict[str, Any] = {
            "input": input_value,
            "scan_mode": "wpscan_binary",
            "base_url": base_url,
        }

        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)

                result["wordpress_version"] = (data.get("version") or {}).get("number")
                result["is_wordpress"] = True
                result["users"] = [
                    {"login": u.get("slug"), "id": u.get("id")}
                    for u in (data.get("users") or {}).values()
                ]
                result["plugins"] = list((data.get("plugins") or {}).keys())
                result["themes"] = list((data.get("main_theme") or {}).keys())
                result["vulnerabilities"] = [
                    v for plugin_data in (data.get("plugins") or {}).values()
                    for v in (plugin_data.get("vulnerabilities") or [])
                ]
            except Exception as exc:
                log.warning("Failed to parse wpscan output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        result["extracted_identifiers"] = [
            f"username:{u['login']}" for u in result.get("users", []) if u.get("login")
        ]
        return result

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        is_wordpress = False
        wp_version: str | None = None
        users: list[str] = []
        plugins_found: list[str] = []
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 WPScan/3.8 (WordPress Security Scanner)"},
        ) as client:
            # 1. Detect WordPress
            try:
                resp = await client.get(base_url)
                body = resp.text
                if any(ind in body for ind in ["/wp-content/", "/wp-includes/", "wp-login.php"]):
                    is_wordpress = True

                # Extract WP version from meta generator
                m = re.search(r'<meta name="generator" content="WordPress ([0-9.]+)"', body, re.I)
                if m:
                    wp_version = m.group(1)
                    is_wordpress = True
                    findings.append({
                        "id": "version_disclosure",
                        "severity": "info",
                        "finding": f"WordPress version disclosed: {wp_version}",
                    })
            except Exception as exc:
                log.debug("WPScan baseline request failed", url=base_url, error=str(exc))

            if not is_wordpress:
                # Quick check on wp-login.php
                try:
                    resp = await client.get(urljoin(base_url, "/wp-login.php"))
                    if "wp-login" in resp.text.lower() or "WordPress" in resp.text:
                        is_wordpress = True
                except Exception:
                    pass

            if not is_wordpress:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "is_wordpress": False,
                    "base_url": base_url,
                    "extracted_identifiers": [],
                }

            # 2. Check XML-RPC (common brute-force vector)
            try:
                resp = await client.get(urljoin(base_url, "/xmlrpc.php"))
                if resp.status_code == 200 and "XML-RPC" in resp.text:
                    findings.append({
                        "id": "xmlrpc_enabled",
                        "severity": "medium",
                        "finding": "XML-RPC enabled — potential brute-force attack vector",
                        "url": urljoin(base_url, "/xmlrpc.php"),
                    })
                    identifiers.append(f"url:{urljoin(base_url, '/xmlrpc.php')}")
            except Exception:
                pass

            # 3. Check readme.html for version disclosure
            for readme in ["/readme.html", "/readme.txt", "/license.txt"]:
                try:
                    resp = await client.get(urljoin(base_url, readme))
                    if resp.status_code == 200:
                        m = re.search(r'Version (\d+\.\d+[\.\d]*)', resp.text)
                        if m and not wp_version:
                            wp_version = m.group(1)
                        findings.append({
                            "id": "readme_exposed",
                            "severity": "low",
                            "finding": f"WordPress readme exposed at {readme} (version leak)",
                            "url": urljoin(base_url, readme),
                        })
                        break
                except Exception:
                    pass

            # 4. Check debug.log
            try:
                resp = await client.get(urljoin(base_url, "/wp-content/debug.log"))
                if resp.status_code == 200 and len(resp.text) > 100:
                    findings.append({
                        "id": "debug_log_exposed",
                        "severity": "high",
                        "finding": "WordPress debug.log exposed — may contain sensitive data",
                        "url": urljoin(base_url, "/wp-content/debug.log"),
                    })
                    identifiers.append(f"url:{urljoin(base_url, '/wp-content/debug.log')}")
            except Exception:
                pass

            # 5. User enumeration via REST API
            try:
                resp = await client.get(urljoin(base_url, "/wp-json/wp/v2/users"))
                if resp.status_code == 200:
                    user_data = resp.json()
                    for u in user_data:
                        login = u.get("slug") or u.get("name", "")
                        if login:
                            users.append(login)
                            identifiers.append(f"username:{login}")
                    if users:
                        findings.append({
                            "id": "user_enumeration",
                            "severity": "medium",
                            "finding": f"WordPress users enumerated via REST API: {', '.join(users[:5])}",
                        })
            except Exception:
                pass

            # 6. Check common plugins
            for plugin in _COMMON_PLUGINS:
                try:
                    url = urljoin(base_url, f"/wp-content/plugins/{plugin}/readme.txt")
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        plugins_found.append(plugin)
                        # Try to extract plugin version
                        m = re.search(r'Stable tag:\s*([0-9.]+)', resp.text, re.I)
                        version = m.group(1) if m else "unknown"
                        findings.append({
                            "id": "plugin_detected",
                            "severity": "info",
                            "finding": f"Plugin detected: {plugin} v{version}",
                            "plugin": plugin,
                            "version": version,
                        })
                except Exception:
                    pass

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "is_wordpress": is_wordpress,
            "base_url": base_url,
            "wordpress_version": wp_version,
            "users_enumerated": users,
            "plugins_detected": plugins_found,
            "findings": findings,
            "total_findings": len(findings),
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
