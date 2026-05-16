"""LinkFinder — JavaScript endpoint and secret extractor.

LinkFinder discovers endpoints, URLs, and sensitive strings hidden inside
JavaScript files of web applications — a goldmine for attack surface mapping.

Manual-only scanner (LinkFinder Python script wraps the same HTTP logic).
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Endpoint patterns in JavaScript
_JS_ENDPOINT_PATTERNS: list[tuple[str, str]] = [
    # REST API endpoints
    (r"""(?:"|')(/(?:api|v\d+|rest|graphql|auth|admin|internal|private|user|account|dashboard|data|search|upload|webhook|token|oauth)/[^"'<>\s]{1,200})(?:"|')""", "api_endpoint"),
    # Relative paths
    (r"""(?:"|')(/?[a-zA-Z0-9_\-/]+\.(?:php|asp|aspx|jsp|json|xml|do|action|html)(?:\?[^"'<>\s]*)?)(?:"|')""", "server_endpoint"),
    # Full URLs
    (r"""(?:"|')(https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{10,200})(?:"|')""", "full_url"),
    # Fetch/XHR calls
    (r"""(?:fetch|axios|xhr\.open|\.get|\.post|\.put|\.delete|\.patch)\s*\((?:"|')([^"']{5,200})(?:"|')""", "xhr_call"),
    # GraphQL queries
    (r"""(?:query|mutation)\s+\w+\s*\{[^}]{10,}""", "graphql_operation"),
    # WebSocket endpoints
    (r"""new\s+WebSocket\s*\((?:"|')([^"']+)(?:"|')""", "websocket_endpoint"),
]

# Secret/sensitive data patterns in JS
_JS_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, secret_type, severity)
    (r"(?i)api.?key\s*[=:]\s*['\"]([A-Za-z0-9\-_]{20,})['\"]", "api_key", "critical"),
    (r"(?i)(?:secret|private).?key\s*[=:]\s*['\"]([A-Za-z0-9\-_/+=]{16,})['\"]", "secret_key", "critical"),
    (r"(?i)token\s*[=:]\s*['\"]([A-Za-z0-9\-_.]{20,})['\"]", "token", "high"),
    (r"(?i)password\s*[=:]\s*['\"]([^'\"]{8,})['\"]", "password", "critical"),
    (r"(?i)auth\s*[=:]\s*['\"]([A-Za-z0-9\-_.]{20,})['\"]", "auth_token", "high"),
    (r"AIza[0-9A-Za-z\-_]{35}", "google_api_key", "high"),
    (r"(?i)stripe[_\-]?(?:secret|publishable)[_\-]?key\s*[=:]\s*['\"]([spk]{2}_[a-zA-Z0-9]{24,})", "stripe_key", "critical"),
    (r"sk-[a-zA-Z0-9]{48}", "openai_key", "critical"),
    (r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.", "jwt_token", "medium"),
    (r"(?i)firebase[_\-]?(?:api[_\-]?key|config)\s*[=:]\s*['\"]([A-Za-z0-9\-_]{30,})", "firebase_config", "high"),
    (r"(?i)(?:aws|amazon)[_\-]?(?:access[_\-]?key|secret)\s*[=:]\s*['\"]([A-Z0-9]{20,})", "aws_key", "critical"),
]

# Interesting comment patterns in JS
_COMMENT_PATTERNS: list[tuple[str, str]] = [
    (r"//\s*(?:TODO|FIXME|HACK|XXX|BUG|TEMP|TEMPORARY).*?(?:password|secret|key|token|auth|admin)", "sensitive_todo"),
    (r"/\*[\s\S]*?(?:password|secret|api.?key|token|auth)[\s\S]*?\*/", "sensitive_comment"),
    (r"//.*(?:prod|production|live)[_\- ](?:password|secret|key|token)", "prod_secret_comment"),
]


class LinkFinderScanner(BaseOsintScanner):
    """JavaScript endpoint and secret extractor.

    Fetches and analyses JavaScript bundles from the target web application
    to discover hidden API endpoints, WebSocket URLs, GraphQL operations,
    hardcoded credentials, and API keys.
    """

    scanner_name = "linkfinder"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        js_files_found: list[str] = []
        all_endpoints: list[dict[str, Any]] = []
        secrets_found: list[dict[str, Any]] = []
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        base_domain = parsed.hostname

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LinkFinder/1.0)"},
        ) as client:
            # Step 1: Fetch HTML and extract JS file references
            try:
                resp = await client.get(base_url)
                html = resp.text

                # Find all script src attributes
                js_refs = re.findall(r'<script[^>]+src\s*=\s*["\']([^"\']+)["\']', html, re.I)
                # Also find inline script blocks for direct analysis
                inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.I)

                for js_ref in js_refs:
                    if js_ref.startswith("http"):
                        full_url = js_ref
                    else:
                        full_url = urljoin(base_url, js_ref)
                    if base_domain in full_url or js_ref.startswith("/"):
                        js_files_found.append(full_url)

            except Exception as exc:
                log.debug("LinkFinder HTML fetch failed", url=base_url, error=str(exc))
                html = ""
                inline_scripts = []

            # Step 2: Fetch each JS file and extract endpoints/secrets
            semaphore = asyncio.Semaphore(5)

            async def analyse_js(js_url: str, js_content: str | None = None) -> None:
                async with semaphore:
                    if js_content is None:
                        try:
                            resp = await client.get(js_url)
                            if resp.status_code != 200:
                                return
                            js_content = resp.text
                        except Exception:
                            return

                    if not js_content or len(js_content) < 10:
                        return

                    # Extract endpoints
                    for pattern, ep_type in _JS_ENDPOINT_PATTERNS:
                        for match in re.finditer(pattern, js_content, re.I):
                            endpoint = match.group(1).strip()
                            if len(endpoint) < 3 or endpoint.startswith("//"):
                                continue
                            # Make absolute if relative
                            if endpoint.startswith("/"):
                                endpoint = urljoin(base_url, endpoint)
                            entry = {
                                "endpoint": endpoint,
                                "type": ep_type,
                                "source": js_url if js_url != "inline" else "inline_script",
                            }
                            # Dedup
                            if not any(e["endpoint"] == endpoint for e in all_endpoints):
                                all_endpoints.append(entry)
                                if ep_type in ("api_endpoint", "xhr_call", "websocket_endpoint"):
                                    identifiers.append(f"url:{endpoint}")

                    # Extract secrets
                    for pattern, secret_type, severity in _JS_SECRET_PATTERNS:
                        for match in re.finditer(pattern, js_content, re.I):
                            value = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
                            truncated = value[:20] + "..." if len(value) > 20 else value
                            secret_entry = {
                                "type": secret_type,
                                "severity": severity,
                                "evidence": truncated,
                                "source": js_url if js_url != "inline" else "inline_script",
                            }
                            key = f"{secret_type}:{truncated}"
                            if not any(f"{s['type']}:{s['evidence']}" == key for s in secrets_found):
                                secrets_found.append(secret_entry)
                                ident = f"secret:{secret_type}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

            # Analyse fetched JS files
            js_tasks = [analyse_js(url) for url in js_files_found[:15]]
            # Analyse inline scripts
            for script in inline_scripts[:5]:
                js_tasks.append(analyse_js("inline", script))

            await asyncio.gather(*js_tasks)

        # Categorize endpoints
        endpoint_categories: dict[str, list[str]] = {}
        for ep in all_endpoints:
            cat = ep["type"]
            if cat not in endpoint_categories:
                endpoint_categories[cat] = []
            endpoint_categories[cat].append(ep["endpoint"])

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "js_files_analysed": len(js_files_found),
            "js_files": js_files_found[:20],
            "endpoints": all_endpoints[:100],
            "total_endpoints": len(all_endpoints),
            "endpoint_categories": {k: v[:10] for k, v in endpoint_categories.items()},
            "secrets_found": secrets_found[:20],
            "total_secrets": len(secrets_found),
            "extracted_identifiers": identifiers[:100],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
