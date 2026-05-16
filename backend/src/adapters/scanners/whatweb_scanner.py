"""WhatWeb — web technology fingerprinting scanner.

WhatWeb identifies 1800+ web technologies including CMS, blogging platforms,
JavaScript frameworks, analytics tools, load balancers, CDNs, and more.

Two-mode operation:
1. **whatweb binary** — if on PATH, invoked with JSON output for full detection
2. **Manual fallback** — HTTP response fingerprinting (headers, HTML patterns, cookies)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Tech fingerprints: (tech_name, category, match_type, pattern)
_TECH_SIGNATURES: list[tuple[str, str, str, str]] = [
    # JavaScript frameworks
    ("React", "js_framework", "body", r"(?i)react(?:\.min)?\.js|data-reactroot|__REACT_DEVTOOLS"),
    ("Vue.js", "js_framework", "body", r"(?i)vue(?:\.min)?\.js|data-v-[a-f0-9]+|__vue__"),
    ("Angular", "js_framework", "body", r"(?i)angular(?:\.min)?\.js|ng-version|ng-app"),
    ("jQuery", "js_framework", "body", r"(?i)jquery(?:[.-]\d+)?(?:\.min)?\.js"),
    ("Next.js", "js_framework", "body", r"(?i)_next/static|__NEXT_DATA__"),
    ("Nuxt.js", "js_framework", "body", r"(?i)__nuxt__|_nuxt/"),
    ("Svelte", "js_framework", "body", r"(?i)svelte|__svelte"),
    # CSS frameworks
    ("Bootstrap", "css_framework", "body", r"(?i)bootstrap(?:[.-]\d+)?(?:\.min)?\.css|class=[\"'][^\"']*\bnavbar-"),
    ("Tailwind CSS", "css_framework", "body", r"(?i)tailwind(?:css)?|class=[\"'][^\"']*\b(?:flex|grid|px-|py-|text-[a-z]+-\d{3})"),
    ("Foundation", "css_framework", "body", r"(?i)foundation\.(?:min\.)?css"),
    # Analytics
    ("Google Analytics", "analytics", "body", r"(?i)google-analytics\.com/analytics\.js|gtag\(|UA-\d+-\d+|G-[A-Z0-9]+"),
    ("Google Tag Manager", "analytics", "body", r"(?i)googletagmanager\.com|GTM-[A-Z0-9]+"),
    ("Hotjar", "analytics", "body", r"(?i)hotjar|hj\("),
    ("Matomo", "analytics", "body", r"(?i)matomo|piwik"),
    ("Segment", "analytics", "body", r"(?i)segment\.(?:com|io)|analytics\.js"),
    # Web servers
    ("Nginx", "web_server", "header", r"(?i)nginx"),
    ("Apache", "web_server", "header", r"(?i)apache"),
    ("IIS", "web_server", "header", r"(?i)microsoft-iis"),
    ("Cloudflare", "cdn", "header", r"(?i)cloudflare"),
    ("Akamai", "cdn", "header", r"(?i)akamai|x-akamai"),
    ("Fastly", "cdn", "header", r"(?i)fastly|x-fastly"),
    ("AWS CloudFront", "cdn", "header", r"(?i)cloudfront|x-amz-cf"),
    # Backend frameworks
    ("Ruby on Rails", "framework", "header", r"(?i)X-Powered-By.*rails|Phusion Passenger"),
    ("Django", "framework", "body", r"(?i)csrfmiddlewaretoken|django"),
    ("Laravel", "framework", "cookie", r"(?i)laravel_session|XSRF-TOKEN"),
    ("Express.js", "framework", "header", r"(?i)X-Powered-By.*Express"),
    ("ASP.NET", "framework", "header", r"(?i)X-Powered-By.*ASP\.NET|X-AspNet"),
    ("Flask", "framework", "cookie", r"(?i)session"),
    ("Spring", "framework", "body", r"(?i)spring|org\.springframework"),
    # CMS (beyond cms_detect — version focus)
    ("WordPress", "cms", "body", r"/wp-content/|/wp-includes/"),
    ("Drupal", "cms", "body", r"/sites/default/files/|Drupal\.settings"),
    ("Joomla", "cms", "body", r"/components/com_"),
    ("Shopify", "cms", "body", r"cdn\.shopify\.com"),
    ("Magento", "cms", "body", r"Mage\.Cookies|/skin/frontend/"),
    # Security
    ("reCAPTCHA", "security", "body", r"(?i)recaptcha|google\.com/recaptcha"),
    ("hCaptcha", "security", "body", r"(?i)hcaptcha\.com"),
    ("Cloudflare Turnstile", "security", "body", r"(?i)challenges\.cloudflare\.com"),
    # Payments
    ("Stripe", "payment", "body", r"(?i)stripe\.com/v3|js\.stripe\.com"),
    ("PayPal", "payment", "body", r"(?i)paypal\.com/sdk|paypalobjects\.com"),
    ("Braintree", "payment", "body", r"(?i)braintreepayments|js\.braintreegateway"),
    # Database hints
    ("Elasticsearch", "database", "header", r"(?i)X-elastic|elastic\.co"),
    # UI libraries
    ("Font Awesome", "ui", "body", r"(?i)font-awesome|fa-[a-z]+"),
    ("Material UI", "ui", "body", r"(?i)MuiButton|MaterialUI"),
    ("Ant Design", "ui", "body", r"(?i)ant-design|antd"),
]

# Security header analysis
_SECURITY_HEADERS: list[tuple[str, str]] = [
    ("Strict-Transport-Security", "hsts"),
    ("Content-Security-Policy", "csp"),
    ("X-Frame-Options", "x_frame_options"),
    ("X-XSS-Protection", "x_xss_protection"),
    ("X-Content-Type-Options", "x_content_type_options"),
    ("Referrer-Policy", "referrer_policy"),
    ("Permissions-Policy", "permissions_policy"),
    ("Cross-Origin-Opener-Policy", "coop"),
    ("Cross-Origin-Embedder-Policy", "coep"),
    ("Cross-Origin-Resource-Policy", "corp"),
]


class WhatWebScanner(BaseOsintScanner):
    """Web technology fingerprinting scanner.

    Identifies 40+ technology categories: JS/CSS frameworks, analytics tools,
    CDNs, web servers, CMS platforms, payment processors, security tools.
    Also audits security headers and provides a security posture score.
    """

    scanner_name = "whatweb"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 43200  # 12h — tech stack changes rarely
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("whatweb"):
            return await self._run_whatweb_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_whatweb_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"whatweb_{run_id}.json")
        cmd = [
            "whatweb",
            base_url,
            "--log-json", out_file,
            "--color=never",
            "--no-errors",
            "-a", "3",
            "-q",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 5)
        except asyncio.TimeoutError:
            log.warning("whatweb timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        technologies: dict[str, Any] = {}
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if isinstance(data, list):
                                for entry in data:
                                    for plugin_name, plugin_data in entry.get("plugins", {}).items():
                                        technologies[plugin_name] = plugin_data
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception as exc:
                log.warning("Failed to parse whatweb output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        return {
            "input": input_value,
            "scan_mode": "whatweb_binary",
            "base_url": base_url,
            "technologies": technologies,
            "total_technologies": len(technologies),
            "extracted_identifiers": [f"tech:{t}" for t in technologies],
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        technologies: dict[str, list[str]] = {}
        security_headers: dict[str, str] = {}
        missing_security_headers: list[str] = []
        server_info: dict[str, str] = {}

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WhatWeb/0.5)"},
        ) as client:
            try:
                resp = await client.get(base_url)
                body = resp.text
                headers_str = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
                cookies_str = " ".join(resp.headers.get("set-cookie", "").split(";"))

                # Collect server/version headers
                for hdr in ["Server", "X-Powered-By", "X-Generator", "X-Runtime", "X-Framework"]:
                    val = resp.headers.get(hdr, "")
                    if val:
                        server_info[hdr] = val

                # Run fingerprints
                for tech_name, category, match_type, pattern in _TECH_SIGNATURES:
                    matched = False
                    if match_type == "body":
                        matched = bool(re.search(pattern, body))
                    elif match_type == "header":
                        matched = bool(re.search(pattern, headers_str, re.I))
                    elif match_type == "cookie":
                        matched = bool(re.search(pattern, cookies_str, re.I))

                    if matched:
                        if category not in technologies:
                            technologies[category] = []
                        if tech_name not in technologies[category]:
                            technologies[category].append(tech_name)

                # Security headers audit
                for header_name, header_key in _SECURITY_HEADERS:
                    val = resp.headers.get(header_name, "")
                    if val:
                        security_headers[header_key] = val
                    else:
                        missing_security_headers.append(header_name)

            except Exception as exc:
                log.debug("WhatWeb fingerprint failed", url=base_url, error=str(exc))

        # Compute security score (0-100)
        max_score = len(_SECURITY_HEADERS)
        security_score = int(((max_score - len(missing_security_headers)) / max_score) * 100)

        all_technologies = [t for techs in technologies.values() for t in techs]

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "technologies_by_category": technologies,
            "all_technologies": all_technologies,
            "total_technologies": len(all_technologies),
            "server_info": server_info,
            "security_headers": security_headers,
            "missing_security_headers": missing_security_headers,
            "security_header_score": security_score,
            "extracted_identifiers": [f"tech:{t}" for t in all_technologies],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
