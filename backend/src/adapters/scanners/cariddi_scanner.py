"""Cariddi — web crawler for endpoint collection and secrets detection.

Cariddi crawls web targets to discover all endpoints, forms, parameters,
and potential secrets. Great for mapping the full attack surface of a web app.

Two-mode operation:
1. **cariddi binary** — if on PATH, invoked for full crawl with JSON output
2. **Manual fallback** — BFS HTTP crawler with endpoint/form/secret extraction
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Patterns for interesting findings during crawl
_ENDPOINT_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)/api/", "api_endpoint"),
    (r"(?i)/admin", "admin_endpoint"),
    (r"(?i)/upload", "upload_endpoint"),
    (r"(?i)/download", "download_endpoint"),
    (r"(?i)/export", "export_endpoint"),
    (r"(?i)/import", "import_endpoint"),
    (r"(?i)/graphql", "graphql_endpoint"),
    (r"(?i)/webhook", "webhook_endpoint"),
    (r"(?i)/callback", "callback_endpoint"),
    (r"(?i)/oauth", "oauth_endpoint"),
    (r"(?i)/token", "token_endpoint"),
    (r"(?i)\.(php|asp|aspx|jsp)", "server_side_script"),
]

_SECRET_PATTERNS_INLINE: list[tuple[str, str]] = [
    (r"(?i)api.?key\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{20,}", "api_key_in_page"),
    (r"(?i)token\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{20,}", "token_in_page"),
    (r"(?i)secret\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{16,}", "secret_in_page"),
    (r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.", "jwt_in_page"),
    (r"(?:AKIA)[A-Z0-9]{16}", "aws_key_in_page"),
    (r"(?i)password\s*[=:]\s*['\"][^'\"]{8,}", "password_in_page"),
]

_MAX_CRAWL_PAGES = 50
_MAX_CRAWL_DEPTH = 3


class CariddiScanner(BaseOsintScanner):
    """Web crawler for endpoint and secret discovery.

    Crawls the target web application, collecting:
    - All discovered URLs and endpoints
    - HTML forms (action URLs, method, fields)
    - Query parameters per endpoint
    - Potential in-page secrets / tokens
    - JavaScript file references
    - Interesting endpoint categories (API, admin, upload, etc.)
    """

    scanner_name = "cariddi"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 150

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("cariddi"):
            return await self._run_cariddi_binary(base_url, input_value)
        return await self._manual_crawl(base_url, input_value)

    async def _run_cariddi_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"cariddi_{run_id}.json")
        cmd = [
            "cariddi",
            "-e",
            "-s",
            "-err",
            "-json",
            "-d", "2",
            "-i", "20",
            "-o", out_file,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                proc.stdin.write(f"{base_url}\n".encode())
                await proc.stdin.drain()
                proc.stdin.close()
                await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 15)
            except asyncio.TimeoutError:
                log.warning("cariddi timed out", url=base_url)
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception as exc:
            log.debug("cariddi binary failed", error=str(exc))

        endpoints: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            endpoints.append({
                                "url": entry.get("url", ""),
                                "parameters": entry.get("parameters", []),
                                "errors": entry.get("errors", []),
                            })
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception as exc:
                log.warning("Failed to parse cariddi output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"url:{e['url']}" for e in endpoints if e.get("url")]
        return {
            "input": input_value,
            "scan_mode": "cariddi_binary",
            "base_url": base_url,
            "endpoints": endpoints,
            "total_endpoints": len(endpoints),
            "extracted_identifiers": identifiers[:100],
        }

    async def _manual_crawl(self, base_url: str, input_value: str) -> dict[str, Any]:
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(base_url, 0)])
        discovered_urls: list[str] = []
        forms: list[dict[str, Any]] = []
        params_by_url: dict[str, list[str]] = {}
        secrets_found: list[dict[str, Any]] = []
        js_files: list[str] = []
        interesting_endpoints: dict[str, list[str]] = {}
        identifiers: list[str] = []

        parsed_base = urlparse(base_url)
        base_domain = parsed_base.hostname

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Cariddi/1.0)"},
        ) as client:
            while queue and len(visited) < _MAX_CRAWL_PAGES:
                current_url, depth = queue.popleft()
                if current_url in visited or depth > _MAX_CRAWL_DEPTH:
                    continue
                visited.add(current_url)

                try:
                    resp = await client.get(current_url)
                    if resp.status_code not in (200, 301, 302):
                        continue
                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type and "javascript" not in content_type:
                        continue

                    body = resp.text
                    discovered_urls.append(current_url)

                    # Check for secrets in page
                    for pattern, secret_type in _SECRET_PATTERNS_INLINE:
                        if re.search(pattern, body):
                            secrets_found.append({
                                "url": current_url,
                                "type": secret_type,
                                "severity": "high",
                            })
                            ident = f"secret:{secret_type}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    # Extract all links
                    href_pattern = re.compile(r'(?i)(?:href|src|action)\s*=\s*["\']([^"\']+)["\']')
                    for match in href_pattern.finditer(body):
                        href = match.group(1).strip()
                        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                            continue
                        full_url = urljoin(current_url, href).split("#")[0]
                        parsed_link = urlparse(full_url)
                        # Stay on same domain
                        if parsed_link.hostname != base_domain:
                            continue
                        # Track query params
                        if parsed_link.query:
                            params = list(parse_qs(parsed_link.query).keys())
                            clean = full_url.split("?")[0]
                            if clean not in params_by_url:
                                params_by_url[clean] = []
                            params_by_url[clean].extend(
                                p for p in params if p not in params_by_url[clean]
                            )
                        # Queue for crawling
                        if full_url not in visited:
                            queue.append((full_url, depth + 1))
                        # Detect interesting endpoints
                        for ep_pattern, ep_type in _ENDPOINT_PATTERNS:
                            if re.search(ep_pattern, full_url):
                                if ep_type not in interesting_endpoints:
                                    interesting_endpoints[ep_type] = []
                                if full_url not in interesting_endpoints[ep_type]:
                                    interesting_endpoints[ep_type].append(full_url)
                                break
                        # Track JS files
                        if full_url.endswith(".js") and full_url not in js_files:
                            js_files.append(full_url)

                    # Extract forms
                    form_pattern = re.compile(
                        r'(?i)<form[^>]*(?:action\s*=\s*["\']([^"\']*)["\'])?[^>]*>(.*?)</form>',
                        re.DOTALL,
                    )
                    for form_match in form_pattern.finditer(body):
                        action = form_match.group(1) or current_url
                        form_body = form_match.group(2)
                        method_m = re.search(r'(?i)method\s*=\s*["\']([^"\']+)["\']', body)
                        method = method_m.group(1).upper() if method_m else "GET"
                        # Extract input names
                        inputs = re.findall(r'(?i)<input[^>]+name\s*=\s*["\']([^"\']+)["\']', form_body)
                        full_action = urljoin(current_url, action)
                        forms.append({
                            "action": full_action,
                            "method": method,
                            "fields": inputs,
                        })

                except Exception as exc:
                    log.debug("Cariddi crawl request failed", url=current_url, error=str(exc))

        # Build final URL identifiers
        for url in discovered_urls[:50]:
            ident = f"url:{url}"
            if ident not in identifiers:
                identifiers.append(ident)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "pages_crawled": len(visited),
            "discovered_urls": discovered_urls[:200],
            "total_urls": len(discovered_urls),
            "forms": forms[:20],
            "total_forms": len(forms),
            "parameters_by_url": {k: v for k, v in list(params_by_url.items())[:20]},
            "js_files": js_files[:20],
            "interesting_endpoints": {k: v[:5] for k, v in interesting_endpoints.items()},
            "secrets_found": secrets_found[:10],
            "extracted_identifiers": identifiers[:100],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value.rstrip("/")
