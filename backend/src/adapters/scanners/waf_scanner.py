"""WAF detection scanner — fingerprints Web Application Firewalls via HTTP probes."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Known WAF fingerprints keyed by (vendor, name).
# Each entry maps to a list of (header_name, regex_pattern) tuples.
_HEADER_SIGNATURES: list[tuple[str, str, str, str]] = [
    # (vendor, name, header_name, regex_pattern)
    ("Cloudflare", "Cloudflare", "CF-RAY", r".+"),
    ("Cloudflare", "Cloudflare", "Server", r"cloudflare"),
    ("Sucuri", "Sucuri CloudProxy", "X-Sucuri-ID", r".+"),
    ("Sucuri", "Sucuri CloudProxy", "X-Sucuri-Cache", r".+"),
    ("Akamai", "Akamai Ghost", "Server", r"AkamaiGHost"),
    ("Akamai", "Akamai", "X-Check-Cacheable", r".+"),
    ("Imperva", "Incapsula", "X-CDN", r"Incapsula"),
    ("Imperva", "Incapsula", "X-Iinfo", r".+"),
    ("F5", "BIG-IP ASM", "X-Wa-Info", r".+"),
    ("F5", "BIG-IP APM", "X-WA-Info", r".+"),
    ("Barracuda", "Barracuda WAF", "X-Barracuda-Protection", r".+"),
    ("AWS", "AWS WAF", "X-AMZ-CF-ID", r".+"),
    ("Fastly", "Fastly WAF", "X-Served-By", r"cache-"),
    ("Plesk", "Plesk", "X-Powered-By-Plesk", r".+"),
    ("ModSecurity", "ModSecurity", "X-Mod-Security-Message", r".+"),
    ("Wallarm", "Wallarm", "X-Wallarm-Node", r".+"),
    ("Reblaze", "Reblaze", "X-Reblaze-Protection", r".+"),
    ("DenyAll", "DenyAll", "X-DenyAll-Protection", r".+"),
    ("Citrix", "Citrix NetScaler", "Via", r"NS-CACHE"),
    ("Fortinet", "FortiWeb", "X-Protected-By", r"FortiWeb"),
    ("Palo Alto", "PAN-DB", "X-Palo-Alto-URL", r".+"),
    ("Microsoft", "Azure Front Door", "X-Azure-Ref", r".+"),
]

# Response body patterns that indicate a WAF block page
_BODY_SIGNATURES: list[tuple[str, str, str]] = [
    # (vendor, name, regex_pattern)
    ("Cloudflare", "Cloudflare", r"<title>.*?Cloudflare.*?</title>"),
    ("Cloudflare", "Cloudflare", r"cf-error-details"),
    ("Sucuri", "Sucuri CloudProxy", r"Sucuri WebSite Firewall"),
    ("Imperva", "Incapsula", r"/_Incapsula_Resource"),
    ("Imperva", "Incapsula", r"incapsula incident id"),
    ("Barracuda", "Barracuda WAF", r"Barracuda Networks.*?blocked"),
    ("ModSecurity", "ModSecurity", r"ModSecurity.*?Intervention"),
    ("Akamai", "Akamai", r"AkamaiGHost"),
    ("F5", "BIG-IP ASM", r"The requested URL was rejected.*?F5"),
    ("Fortinet", "FortiWeb", r"FortiWeb Application Security"),
    ("Reblaze", "Reblaze", r"reblaze"),
    ("AWS", "AWS WAF", r"AWS WAF"),
]

# WAF-detection probe payloads — these trigger WAF rules without causing real harm
_PROBE_PARAMS = [
    ("xss_probe", "?q=<script>alert(1)</script>"),
    ("sqli_probe", "?id=1' OR '1'='1"),
    ("path_traversal", "?file=../../etc/passwd"),
]


class WAFDetectScanner(BaseOsintScanner):
    """Fingerprints WAF presence by sending known probe requests and analysing HTTP responses.

    Uses httpx to send multiple probes to the target (DOMAIN or URL):
    1. Baseline request with a custom scan-signature header
    2. XSS payload probe
    3. SQLi payload probe
    4. Path traversal probe

    Response headers and body are matched against a catalogue of known WAF signatures.
    Returns enrichment-only data (no pivot identifiers extracted).
    """

    scanner_name = "waf_detect"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = self._normalise_url(input_value, input_type)

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            },
        ) as client:
            try:
                return await self._detect(client, input_value, base_url)
            except Exception as e:
                log.error("WAF detect scan failed", input=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

    def _normalise_url(self, input_value: str, input_type: ScanInputType) -> str:
        if input_type == ScanInputType.URL:
            parsed = urlparse(input_value)
            return f"{parsed.scheme}://{parsed.netloc}/"
        # DOMAIN — assume HTTPS
        domain = input_value.rstrip("/")
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
        return domain.rstrip("/") + "/"

    async def _detect(
        self, client: httpx.AsyncClient, input_value: str, base_url: str
    ) -> dict[str, Any]:
        detected_headers: list[str] = []
        waf_candidates: dict[tuple[str, str], int] = {}  # (vendor, name) -> hit count

        def _check_headers(headers: httpx.Headers, method: str) -> None:
            for vendor, name, header, pattern in _HEADER_SIGNATURES:
                value = headers.get(header, "")
                if value and re.search(pattern, value, re.IGNORECASE):
                    key = (vendor, name)
                    waf_candidates[key] = waf_candidates.get(key, 0) + 1
                    detected_headers.append(f"{method}:{header}={value[:80]}")

        def _check_body(body: str, method: str) -> None:
            for vendor, name, pattern in _BODY_SIGNATURES:
                if re.search(pattern, body, re.IGNORECASE):
                    key = (vendor, name)
                    waf_candidates[key] = waf_candidates.get(key, 0) + 1

        # Probe 1: baseline with scan-signature header
        try:
            resp = await client.get(
                base_url,
                headers={"X-Scan-Sig": "waf-test-probe"},
            )
            _check_headers(resp.headers, "baseline")
            _check_body(resp.text[:4096], "baseline")
        except Exception as e:
            log.debug("WAF baseline probe failed", url=base_url, error=str(e))

        # Probes 2-4: payload-based probes
        for probe_name, suffix in _PROBE_PARAMS:
            probe_url = base_url.rstrip("/") + "/" + suffix
            try:
                resp = await client.get(probe_url)
                _check_headers(resp.headers, probe_name)
                # Only check body for block responses (40x status codes typically)
                if resp.status_code in (400, 403, 406, 429, 503):
                    _check_body(resp.text[:4096], probe_name)
            except Exception as e:
                log.debug("WAF probe failed", probe=probe_name, url=probe_url, error=str(e))

        waf_detected = bool(waf_candidates)
        waf_name = ""
        waf_vendor = ""
        confidence = 0.0
        fingerprint_method = "header_and_body_analysis"

        if waf_candidates:
            # Pick the highest-confidence match
            best = max(waf_candidates.items(), key=lambda kv: kv[1])
            (waf_vendor, waf_name), hit_count = best
            # Confidence: each hit adds 25% capped at 100%
            confidence = min(1.0, hit_count * 0.25)

        # Deduplicate detected_headers
        detected_headers = list(dict.fromkeys(detected_headers))

        return {
            "input": input_value,
            "found": waf_detected,
            "waf_detected": waf_detected,
            "waf_name": waf_name,
            "waf_vendor": waf_vendor,
            "confidence": round(confidence, 2),
            "detected_headers": detected_headers,
            "fingerprint_method": fingerprint_method,
            "candidate_wafs": [
                {"vendor": v, "name": n, "hits": c}
                for (v, n), c in sorted(waf_candidates.items(), key=lambda kv: -kv[1])
            ],
            "extracted_identifiers": [],  # Enrichment only — no new pivot identifiers
        }
