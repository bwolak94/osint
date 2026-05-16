"""GAU (GetAllUrls) — harvest URLs from Wayback Machine, OTX, Common Crawl, URLScan.

GetAllUrls fetches known URLs for a domain from multiple passive sources without
active scanning. Critical for attack surface mapping and finding forgotten endpoints.

Two-mode operation:
1. **gau binary** — if on PATH, full URL harvest
2. **Manual fallback** — queries Wayback CDX API and URLScan directly
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, urljoin
import shutil
import os
import tempfile

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Interesting URL patterns to flag
_INTERESTING_PATTERNS: list[tuple[str, str]] = [
    (r"\.(sql|db|sqlite|bak|backup)(\?|$)", "database_file"),
    (r"\.(log|txt|csv|tsv)(\?|$)", "log_or_data_file"),
    (r"\.(zip|tar\.gz|tar\.bz2|7z|rar)(\?|$)", "archive_file"),
    (r"\.(env|conf|config|cfg|ini|yaml|yml|json)(\?|$)", "config_file"),
    (r"(password|passwd|secret|token|api.?key|credential)", "credential_leak"),
    (r"(admin|administrator|manage|manager|control)", "admin_endpoint"),
    (r"(debug|test|dev|staging|temp|tmp)", "debug_endpoint"),
    (r"(redirect|return|url|next|goto|forward)\=http", "open_redirect"),
    (r"\.(php|asp|aspx|jsp|jspx)(\?|$)", "server_side_script"),
    (r"(\.git|\.svn|\.hg)/", "vcs_exposure"),
    (r"/api/", "api_endpoint"),
    (r"\?.*=.*(<|%3C|script|onerror|onload)", "xss_parameter"),
    (r"\?.*=(.*SELECT|.*UNION|.*DROP|.*INSERT|.*UPDATE)", "sqli_parameter"),
]


class GAUScanner(BaseOsintScanner):
    """GetAllUrls — passive URL harvesting from multiple archive sources.

    Collects historical and current URLs for the target domain from:
    - Wayback Machine (CDX API)
    - URLScan.io
    - Common Crawl (via index)
    Identifies interesting endpoints, leaked files, and injection points.
    """

    scanner_name = "gau"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400  # 24h — passive data changes slowly
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = _extract_domain(input_value, input_type)
        if not domain:
            return {"input": input_value, "error": "Could not extract domain", "extracted_identifiers": []}

        if shutil.which("gau"):
            return await self._run_gau_binary(domain, input_value)
        return await self._manual_harvest(domain, input_value)

    async def _run_gau_binary(self, domain: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"gau_{run_id}.txt")
        cmd = [
            "gau",
            "--providers", "wayback,urlscan",
            "--threads", "5",
            "--o", out_file,
            domain,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("gau timed out", domain=domain)
            try:
                proc.kill()
            except Exception:
                pass

        urls: list[str] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    urls = [line.strip() for line in fh if line.strip()]
            except Exception as exc:
                log.warning("Failed to read gau output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        interesting = _classify_urls(urls)
        return {
            "input": input_value,
            "scan_mode": "gau_binary",
            "domain": domain,
            "total_urls": len(urls),
            "urls": urls[:500],  # Cap to 500 in result
            "interesting_findings": interesting,
            "extracted_identifiers": [f"url:{u}" for u in interesting.get("all_interesting", [])],
        }

    async def _manual_harvest(self, domain: str, input_value: str) -> dict[str, Any]:
        all_urls: list[str] = []

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GAU/1.0)"},
        ) as client:
            # Source 1: Wayback Machine CDX API
            try:
                cdx_url = (
                    f"https://web.archive.org/cdx/search/cdx"
                    f"?url=*.{domain}/*&output=text&fl=original&collapse=urlkey&limit=1000"
                )
                resp = await client.get(cdx_url)
                if resp.status_code == 200:
                    lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
                    all_urls.extend(lines)
                    log.debug("Wayback CDX returned URLs", domain=domain, count=len(lines))
            except Exception as exc:
                log.debug("Wayback CDX request failed", domain=domain, error=str(exc))

            # Source 2: URLScan.io
            try:
                urlscan_url = f"https://urlscan.io/api/v1/search/?q=domain:{domain}&size=200"
                resp = await client.get(urlscan_url)
                if resp.status_code == 200:
                    data = resp.json()
                    for result in data.get("results", []):
                        page_url = result.get("page", {}).get("url", "")
                        if page_url:
                            all_urls.append(page_url)
                    log.debug("URLScan returned URLs", domain=domain, count=len(data.get("results", [])))
            except Exception as exc:
                log.debug("URLScan request failed", domain=domain, error=str(exc))

        # Deduplicate
        unique_urls = list(dict.fromkeys(all_urls))
        interesting = _classify_urls(unique_urls)

        # Extension breakdown
        ext_counts: dict[str, int] = {}
        for url in unique_urls:
            path = urlparse(url).path
            if "." in path.split("/")[-1]:
                ext = path.rsplit(".", 1)[-1].lower().split("?")[0]
                if len(ext) <= 6:  # Reasonable extension length
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "domain": domain,
            "total_urls": len(unique_urls),
            "urls": unique_urls[:500],
            "interesting_findings": interesting,
            "extension_breakdown": dict(sorted(ext_counts.items(), key=lambda x: -x[1])[:20]),
            "extracted_identifiers": [f"url:{u}" for u in interesting.get("all_interesting", [])[:50]],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _classify_urls(urls: list[str]) -> dict[str, Any]:
    """Classify URLs by interesting patterns."""
    categorized: dict[str, list[str]] = {}
    all_interesting: list[str] = []

    for url in urls:
        for pattern, category in _INTERESTING_PATTERNS:
            if re.search(pattern, url, re.I):
                if category not in categorized:
                    categorized[category] = []
                if url not in categorized[category]:
                    categorized[category].append(url)
                if url not in all_interesting:
                    all_interesting.append(url)
                break

    return {
        **{k: v[:20] for k, v in categorized.items()},  # Cap per-category to 20
        "all_interesting": all_interesting[:100],
        "categories_found": list(categorized.keys()),
        "total_interesting": len(all_interesting),
    }


def _extract_domain(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return value.lstrip("*.").split(":")[0]
    try:
        return urlparse(value).hostname or ""
    except Exception:
        return ""
