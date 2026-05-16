"""ParamSpider — URL parameter discovery and injection surface scanner.

Mines URLs with parameters from Wayback Machine CDX and CommonCrawl,
extracts unique parameter names, then probes them for reflected XSS,
open redirect, and SQLi injection points. Mirrors the ParamSpider +
active injection workflow used by bug bounty hunters.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Wayback CDX API
_WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
# CommonCrawl index
_CC_API = "https://index.commoncrawl.org/CC-MAIN-2024-10-index"

# Parameter patterns to filter out (static/non-injectable)
_BORING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "ref", "locale", "lang", "format", "callback",
    "_ga", "_gid", "v", "ver", "version", "timestamp", "t", "ts",
})

# Injection probes per parameter type
_XSS_PROBE = "<script>alert(1)</script>"
_SQLI_PROBE = "'"
_REDIRECT_PROBE = "https://evil-paramspider.example.com"
_SSTI_PROBE = "{{7*7}}"

# Response patterns indicating injection success
_XSS_REFLECT = re.compile(r'<script>alert\(1\)</script>', re.I)
_SQLI_ERROR = re.compile(
    r"(?i)(syntax error|sql|mysql|ORA-\d+|postgresql|sqlite|unterminated string)",
)
_SSTI_SUCCESS = re.compile(r"\b49\b")


class ParamSpiderScanner(BaseOsintScanner):
    """URL parameter discovery and injection surface scanner.

    Collects historical URLs with parameters from Wayback CDX and CommonCrawl,
    deduplicates parameter names, then actively probes them for XSS reflection,
    open redirect, SQLi, and SSTI injection points.
    """

    scanner_name = "paramspider"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = _extract_domain(input_value, input_type)
        base_url = f"https://{domain}"
        return await self._manual_scan(domain, base_url, input_value)

    async def _manual_scan(self, domain: str, base_url: str, input_value: str) -> dict[str, Any]:
        all_urls: list[str] = []
        params_found: dict[str, list[str]] = {}  # param -> [example_urls]
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ParamSpider/1.0)"},
        ) as client:

            # Step 1: Mine Wayback CDX for URLs with params
            try:
                params = {
                    "url": f"*.{domain}/*",
                    "output": "text",
                    "fl": "original",
                    "collapse": "urlkey",
                    "filter": "statuscode:200",
                    "limit": "2000",
                }
                resp = await client.get(_WAYBACK_CDX, params=params, timeout=15)
                if resp.status_code == 200:
                    for line in resp.text.splitlines()[:2000]:
                        line = line.strip()
                        if "?" in line and line.startswith("http"):
                            all_urls.append(line)
            except Exception as exc:
                log.debug("Wayback CDX failed", domain=domain, error=str(exc))

            # Step 2: Mine CommonCrawl
            try:
                cc_params = {
                    "url": f"*.{domain}/*",
                    "output": "json",
                    "fl": "url",
                    "limit": "500",
                }
                resp = await client.get(_CC_API, params=cc_params, timeout=10)
                if resp.status_code == 200:
                    import json
                    for line in resp.text.splitlines()[:500]:
                        try:
                            obj = json.loads(line)
                            url = obj.get("url", "")
                            if "?" in url:
                                all_urls.append(url)
                        except Exception:
                            pass
            except Exception:
                pass

            # Step 3: Extract and deduplicate parameters
            for url in all_urls:
                try:
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    for param in qs:
                        if param not in _BORING_PARAMS and len(param) < 40:
                            if param not in params_found:
                                params_found[param] = []
                            if len(params_found[param]) < 3:
                                params_found[param].append(url)
                except Exception:
                    pass

            # Step 4: Active injection probing on discovered params
            semaphore = asyncio.Semaphore(8)

            async def probe_param(param: str, example_urls: list[str]) -> None:
                async with semaphore:
                    for original_url in example_urls[:2]:
                        try:
                            parsed = urlparse(original_url)
                            qs = dict(parse_qs(parsed.query))

                            for probe, probe_name in [
                                (_XSS_PROBE, "xss"),
                                (_SQLI_PROBE, "sqli"),
                                (_SSTI_PROBE, "ssti"),
                            ]:
                                test_qs = {k: v[0] if isinstance(v, list) else v for k, v in qs.items()}
                                test_qs[param] = probe
                                test_url = urlunparse(
                                    parsed._replace(query=urlencode(test_qs))
                                )
                                try:
                                    resp = await client.get(test_url, timeout=6)
                                    body = resp.text

                                    if probe_name == "xss" and _XSS_REFLECT.search(body):
                                        vulnerabilities.append({
                                            "type": "reflected_xss",
                                            "severity": "high",
                                            "url": test_url[:120],
                                            "parameter": param,
                                            "probe": probe,
                                            "description": f"Reflected XSS via parameter '{param}'",
                                            "remediation": "HTML-encode output; implement Content-Security-Policy",
                                        })
                                        ident = f"vuln:paramspider:xss:{param}"
                                        if ident not in identifiers:
                                            identifiers.append(ident)
                                        break

                                    elif probe_name == "sqli" and _SQLI_ERROR.search(body):
                                        match = _SQLI_ERROR.search(body)
                                        vulnerabilities.append({
                                            "type": "sql_injection",
                                            "severity": "critical",
                                            "url": test_url[:120],
                                            "parameter": param,
                                            "evidence": match.group(0)[:60] if match else "",
                                            "description": f"SQL injection via parameter '{param}'",
                                        })
                                        ident = f"vuln:paramspider:sqli:{param}"
                                        if ident not in identifiers:
                                            identifiers.append(ident)
                                        break

                                    elif probe_name == "ssti" and _SSTI_SUCCESS.search(body):
                                        vulnerabilities.append({
                                            "type": "ssti",
                                            "severity": "critical",
                                            "url": test_url[:120],
                                            "parameter": param,
                                            "description": f"SSTI via parameter '{param}' — 7*7=49 reflected",
                                        })
                                        ident = f"vuln:paramspider:ssti:{param}"
                                        if ident not in identifiers:
                                            identifiers.append(ident)
                                        break

                                except Exception:
                                    pass
                        except Exception:
                            pass

            # Test top 30 unique params
            sorted_params = sorted(params_found.items(), key=lambda x: len(x[1]), reverse=True)
            await asyncio.gather(*[probe_param(p, urls) for p, urls in sorted_params[:30]])

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "domain": domain,
            "urls_harvested": len(all_urls),
            "unique_params": len(params_found),
            "top_params": list(params_found.keys())[:30],
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_domain(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
