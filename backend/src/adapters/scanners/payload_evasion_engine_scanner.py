"""Payload Evasion Engine — detects WAF/security products protecting the target URL.

Module 117 in the Infrastructure & Exploitation domain. Analyses HTTP response headers,
cookies, and response body characteristics on the user-supplied target URL to identify
the presence of Web Application Firewalls (WAF), CDN security layers, DDoS protection,
and bot management platforms. Returns identified products and educational bypass context.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


# WAF fingerprint definitions: each entry has the product name, detection vectors
# (headers, cookies, body patterns), and bypass education notes.
_WAF_SIGNATURES: list[dict[str, Any]] = [
    {
        "product": "Cloudflare",
        "confidence_weight": 10,
        "headers": ["cf-ray", "cf-request-id", "cf-cache-status", "cf-bgj"],
        "cookies": ["__cflb", "__cfuid", "cf_clearance", "__cf_bm"],
        "server_values": ["cloudflare"],
        "body_patterns": [
            re.compile(r"cloudflare", re.IGNORECASE),
            re.compile(r"Ray ID:", re.IGNORECASE),
        ],
        "bypass_education": [
            "Origin IP discovery via DNS history (SecurityTrails, Shodan) to bypass CDN.",
            "HTTP/1.1 chunked transfer encoding bypass (historical).",
            "cf_clearance cookie extraction from browser session.",
        ],
    },
    {
        "product": "AWS WAF / AWS Shield",
        "confidence_weight": 10,
        "headers": ["x-amzn-requestid", "x-amzn-trace-id", "x-amz-cf-id"],
        "cookies": ["aws-waf-token"],
        "server_values": [],
        "body_patterns": [
            re.compile(r"aws", re.IGNORECASE),
        ],
        "bypass_education": [
            "AWS WAF rules are evaluated per-rule — testing for rule gaps via fuzzing.",
            "Size limit bypass: WAF often has max body inspection size limits.",
            "JSON/XML parsing quirks may bypass regex-based rules.",
        ],
    },
    {
        "product": "Akamai",
        "confidence_weight": 10,
        "headers": ["x-akamai-transformed", "x-check-cacheable", "x-akamai-request-id", "akamai-ghost-ip"],
        "cookies": ["ak_bmsc", "bm_sv", "bm_sz"],
        "server_values": ["akamaighost", "akamai"],
        "body_patterns": [
            re.compile(r"akamai", re.IGNORECASE),
            re.compile(r"Ref \w{18}", re.IGNORECASE),
        ],
        "bypass_education": [
            "Akamai Bot Manager uses JavaScript challenges — headless browser may bypass.",
            "Origin IP discovery via Akamai Pragma headers in error responses.",
            "HTTP/2 rapid reset attacks may circumvent rate limiting (patched).",
        ],
    },
    {
        "product": "F5 BIG-IP ASM",
        "confidence_weight": 10,
        "headers": ["x-cnection", "x-wa-info"],
        "cookies": ["TS", "BIGipServer", "F5_"],
        "server_values": ["bigip"],
        "body_patterns": [
            re.compile(r"Request Rejected", re.IGNORECASE),
            re.compile(r"The requested URL was rejected", re.IGNORECASE),
        ],
        "bypass_education": [
            "F5 ASM evasion: parameter pollution (HPP) — duplicate parameter names.",
            "Unicode encoding of attack payloads may bypass signature matching.",
            "HTTP verb tampering: use uncommon HTTP methods.",
        ],
    },
    {
        "product": "Imperva / Incapsula",
        "confidence_weight": 10,
        "headers": ["x-iinfo", "x-cdn", "incap-ses"],
        "cookies": ["incap_ses", "visid_incap", "_incap_"],
        "server_values": ["imperva", "incapsula"],
        "body_patterns": [
            re.compile(r"incapsula", re.IGNORECASE),
            re.compile(r"Request unsuccessful\. Incapsula", re.IGNORECASE),
        ],
        "bypass_education": [
            "Incapsula: header injection via X-Forwarded-For spoofing (patched in most configs).",
            "Chunked encoding bypass for body inspection evasion.",
            "HTTP/2 pseudo-header manipulation.",
        ],
    },
    {
        "product": "Sucuri",
        "confidence_weight": 10,
        "headers": ["x-sucuri-id", "x-sucuri-cache"],
        "cookies": [],
        "server_values": ["sucuri"],
        "body_patterns": [
            re.compile(r"sucuri", re.IGNORECASE),
            re.compile(r"Access Denied.*Sucuri", re.IGNORECASE),
        ],
        "bypass_education": [
            "Sucuri origin bypass: check for direct IP access and CF-Connecting-IP header leaks.",
            "Sucuri WAF regex evasion via case variation and encoding.",
        ],
    },
    {
        "product": "Fastly",
        "confidence_weight": 10,
        "headers": ["x-fastly-request-id", "fastly-debug-digest", "x-served-by"],
        "cookies": [],
        "server_values": ["varnish", "fastly"],
        "body_patterns": [],
        "bypass_education": [
            "Fastly: origin discovery via certificate SAN enumeration.",
            "Vary header manipulation for cache poisoning.",
        ],
    },
    {
        "product": "ModSecurity",
        "confidence_weight": 8,
        "headers": ["x-modsecurity-score"],
        "cookies": [],
        "server_values": [],
        "body_patterns": [
            re.compile(r"ModSecurity", re.IGNORECASE),
            re.compile(r"This error was generated by Mod_Security", re.IGNORECASE),
            re.compile(r"406 Not Acceptable", re.IGNORECASE),
        ],
        "bypass_education": [
            "ModSecurity OWASP CRS bypass: use multipart boundary fuzzing.",
            "Comment injection in SQL strings: SELECT/*comment*/1.",
            "Case variation and URL encoding of special characters.",
        ],
    },
    {
        "product": "Nginx Rate Limiting / Lua WAF",
        "confidence_weight": 5,
        "headers": [],
        "cookies": [],
        "server_values": ["nginx"],
        "body_patterns": [
            re.compile(r"503 Service Temporarily Unavailable", re.IGNORECASE),
        ],
        "bypass_education": [
            "Nginx rate limiting: distributed requests across multiple IPs.",
            "Lua WAF rules typically inspect specific headers/body fields — probe untested vectors.",
        ],
    },
]


def _fingerprint_waf(
    status_code: int,
    headers: dict[str, str],
    cookies: dict[str, str],
    body: str,
) -> list[dict[str, Any]]:
    """Score each WAF signature against the observed response."""
    detections: list[dict[str, Any]] = []
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
    cookies_lower = {k.lower(): v for k, v in cookies.items()}
    body_lower = body.lower()

    for sig in _WAF_SIGNATURES:
        score = 0
        evidence: list[str] = []

        for h in sig["headers"]:
            if h.lower() in headers_lower:
                score += 3
                evidence.append(f"Header: {h}={headers_lower[h.lower()][:30]}")

        for c in sig["cookies"]:
            for ck in cookies_lower:
                if c.lower() in ck:
                    score += 3
                    evidence.append(f"Cookie: {ck}")
                    break

        for sv in sig["server_values"]:
            if sv.lower() in headers_lower.get("server", ""):
                score += 4
                evidence.append(f"Server header: {headers_lower.get('server', '')}")

        for pattern in sig["body_patterns"]:
            if pattern.search(body):
                score += 2
                evidence.append(f"Body pattern: {pattern.pattern}")

        if score >= 3:
            confidence = "High" if score >= 8 else ("Medium" if score >= 5 else "Low")
            detections.append({
                "product": sig["product"],
                "confidence": confidence,
                "score": score,
                "evidence": evidence,
                "bypass_education": sig["bypass_education"],
            })

    return sorted(detections, key=lambda x: x["score"], reverse=True)


class PayloadEvasionEngineScanner(BaseOsintScanner):
    """Detects WAF and security product presence by analysing HTTP response characteristics.

    Sends a standard GET request to the target URL and fingerprints response headers,
    cookies, and body for signatures of Cloudflare, AWS WAF, Akamai, F5, Imperva,
    Sucuri, Fastly, ModSecurity, and others. Returns detected products with
    educational bypass context (Module 117).
    """

    scanner_name = "payload_evasion_engine"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 14400  # 4 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = input_value.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # Send a normal probe request
            try:
                normal_resp = await client.get(target)
            except httpx.RequestError as exc:
                return {"target": target, "found": False, "error": str(exc)}

            # Send a probe with a benign WAF-triggering pattern in a header
            # (checking if the WAF response changes)
            waf_trigger_resp = None
            try:
                waf_trigger_resp = await client.get(
                    target,
                    headers={
                        "User-Agent": "sqlmap/1.0 (WAF-test-probe)",
                        "X-Scan-Probe": "1' OR '1'='1",
                    },
                )
            except httpx.RequestError:
                pass

        detections = _fingerprint_waf(
            normal_resp.status_code,
            dict(normal_resp.headers),
            dict(normal_resp.cookies),
            normal_resp.text[:50000],
        )

        # Check if WAF triggered on the probe request
        waf_triggered = False
        if waf_trigger_resp is not None:
            if waf_trigger_resp.status_code in (403, 406, 429, 503):
                waf_triggered = True
            elif normal_resp.status_code != waf_trigger_resp.status_code:
                waf_triggered = True

        security_score = sum(d["score"] for d in detections)
        found = len(detections) > 0 or waf_triggered

        return {
            "target": target,
            "found": found,
            "waf_triggered_on_probe": waf_triggered,
            "detected_products": detections,
            "product_count": len(detections),
            "primary_waf": detections[0]["product"] if detections else None,
            "response_metadata": {
                "status_code": normal_resp.status_code,
                "server": normal_resp.headers.get("server", ""),
                "x_powered_by": normal_resp.headers.get("x-powered-by", ""),
                "content_security_policy": bool(normal_resp.headers.get("content-security-policy")),
                "strict_transport_security": bool(normal_resp.headers.get("strict-transport-security")),
                "x_frame_options": normal_resp.headers.get("x-frame-options", ""),
            },
            "educational_note": (
                "WAF detection is the first step in security research against a protected target. "
                "Understanding which product is deployed informs which evasion techniques may be "
                "applicable. Always obtain explicit written authorisation before testing bypasses."
            ),
        }
