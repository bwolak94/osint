"""HTTP probing scanner — web server fingerprinting and technology detection."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Technology fingerprints based on response headers and body patterns
_TECH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("WordPress", re.compile(r"wp-content|wp-includes|wordpress", re.IGNORECASE)),
    ("Drupal", re.compile(r"Drupal|drupal\.js|/sites/default/", re.IGNORECASE)),
    ("Joomla", re.compile(r"Joomla|/components/com_", re.IGNORECASE)),
    ("Laravel", re.compile(r"laravel_session|Laravel", re.IGNORECASE)),
    ("Django", re.compile(r"csrfmiddlewaretoken|django", re.IGNORECASE)),
    ("Rails", re.compile(r"_rails_session|X-Runtime", re.IGNORECASE)),
    ("React", re.compile(r"__react|ReactDOM|react-root", re.IGNORECASE)),
    ("Vue", re.compile(r"__vue|vue\.js|v-app", re.IGNORECASE)),
    ("Angular", re.compile(r"ng-version|angular\.js|ng-app", re.IGNORECASE)),
    ("PHP", re.compile(r"\.php|X-Powered-By: PHP|PHPSESSID", re.IGNORECASE)),
    ("ASP.NET", re.compile(r"ASP\.NET|__VIEWSTATE|X-Powered-By: ASP\.NET", re.IGNORECASE)),
    ("Next.js", re.compile(r"__NEXT_DATA__|x-powered-by: Next\.js", re.IGNORECASE)),
    ("Nuxt.js", re.compile(r"__NUXT__|nuxt\.js", re.IGNORECASE)),
]

# CDN detection based on response headers
_CDN_SIGNATURES: dict[str, list[str]] = {
    "Cloudflare": ["CF-Ray", "cf-cache-status"],
    "Fastly": ["X-Served-By", "Fastly-Debug"],
    "Akamai": ["X-Akamai-Transformed", "X-Check-Cacheable"],
    "CloudFront": ["X-Amz-Cf-Id", "X-Cache: Hit from cloudfront"],
    "Vercel": ["x-vercel-id", "x-vercel-cache"],
    "Netlify": ["x-nf-request-id", "x-netlify"],
}

_COMMON_PATHS = [
    "/robots.txt",
    "/sitemap.xml",
    "/.well-known/security.txt",
    "/crossdomain.xml",
    "/humans.txt",
]


class HttpxProbeScanner(BaseOsintScanner):
    scanner_name = "httpx_probe"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = _normalise_domain(input_value)

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        ) as client:
            # Try HTTPS first, then HTTP
            https_response, redirect_chain, https_available = await _probe_url(
                client, f"https://{domain}"
            )
            if https_response is None:
                http_response, redirect_chain, _ = await _probe_url(
                    client, f"http://{domain}"
                )
                primary = http_response
                https_available = False
            else:
                primary = https_response
                https_available = True

            # Probe common paths
            path_results = await _probe_paths(client, domain, https_available)

        if primary is None:
            return {
                "input": input_value,
                "found": False,
                "error": "Host unreachable",
                "extracted_identifiers": [],
            }

        headers = dict(primary.headers)
        body = primary.text

        title = _extract_title(body)
        technologies = _detect_technologies(headers, body)
        cdn = _detect_cdn(headers)
        hsts = "strict-transport-security" in {k.lower() for k in headers}

        response_headers = {
            "server": headers.get("server") or headers.get("Server"),
            "content-type": headers.get("content-type") or headers.get("Content-Type"),
            "x-powered-by": headers.get("x-powered-by") or headers.get("X-Powered-By"),
            "x-frame-options": headers.get("x-frame-options") or headers.get("X-Frame-Options"),
            "content-security-policy": (
                headers.get("content-security-policy")
                or headers.get("Content-Security-Policy")
            ),
            "strict-transport-security": (
                headers.get("strict-transport-security")
                or headers.get("Strict-Transport-Security")
            ),
        }

        return {
            "input": input_value,
            "found": True,
            "status_code": primary.status_code,
            "title": title,
            "technologies": technologies,
            "cdn": cdn,
            "headers": response_headers,
            "robots_txt": path_results.get("robots_txt"),
            "security_txt": path_results.get("security_txt"),
            "redirect_chain": redirect_chain,
            "https_available": https_available,
            "hsts": hsts,
            "extracted_identifiers": [],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_domain(value: str) -> str:
    value = value.strip()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        return parsed.netloc or value
    return value


async def _probe_url(
    client: httpx.AsyncClient, url: str
) -> tuple[httpx.Response | None, list[str], bool]:
    try:
        resp = await client.get(url)
        chain = [str(r.url) for r in resp.history] + [str(resp.url)]
        return resp, chain, True
    except Exception as exc:
        log.debug("HTTP probe failed", url=url, error=str(exc))
        return None, [], False


async def _probe_paths(
    client: httpx.AsyncClient, domain: str, https: bool
) -> dict[str, str | None]:
    scheme = "https" if https else "http"
    results: dict[str, str | None] = {}

    for path in _COMMON_PATHS:
        url = f"{scheme}://{domain}{path}"
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                key = path.lstrip("/").replace(".", "_").replace("/", "_").replace("-", "_")
                results[key] = resp.text[:2000]
        except Exception:
            pass

    return results


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _detect_technologies(headers: dict[str, str], body: str) -> list[str]:
    combined = " ".join(f"{k}: {v}" for k, v in headers.items()) + " " + body
    detected: list[str] = []
    for tech, pattern in _TECH_PATTERNS:
        if pattern.search(combined):
            detected.append(tech)
    return detected


def _detect_cdn(headers: dict[str, str]) -> str | None:
    lower_headers = {k.lower(): v for k, v in headers.items()}
    for cdn_name, signatures in _CDN_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in lower_headers:
                return cdn_name
    return None
