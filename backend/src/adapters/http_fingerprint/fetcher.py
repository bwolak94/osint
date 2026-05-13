"""HTTP response fingerprinting — tech stack & security headers analysis."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
import httpx

# Technology signatures: {header_or_body_pattern: tech_name}
_TECH_SIGNATURES: list[tuple[str, str, str]] = [
    # (source, pattern, tech)
    ("header:server", r"nginx", "nginx"),
    ("header:server", r"apache", "Apache"),
    ("header:server", r"cloudflare", "Cloudflare"),
    ("header:server", r"lighttpd", "lighttpd"),
    ("header:server", r"iis", "IIS"),
    ("header:server", r"caddy", "Caddy"),
    ("header:x-powered-by", r"php", "PHP"),
    ("header:x-powered-by", r"asp\.net", "ASP.NET"),
    ("header:x-powered-by", r"express", "Express.js"),
    ("header:x-generator", r"wordpress", "WordPress"),
    ("header:x-drupal-cache", r".*", "Drupal"),
    ("header:x-shopify-stage", r".*", "Shopify"),
    ("body", r"wp-content", "WordPress"),
    ("body", r"Joomla!", "Joomla"),
    ("body", r"__next", "Next.js"),
    ("body", r"__nuxt", "Nuxt.js"),
    ("body", r"react\.production\.min\.js", "React"),
    ("body", r"vue\.runtime\.", "Vue.js"),
    ("body", r"angular(?:js)?\.min\.js", "Angular"),
    ("body", r"gtag\(", "Google Analytics"),
    ("body", r"cdn\.shopify\.com", "Shopify"),
]

_SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "x-xss-protection",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-embedder-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
]


@dataclass
class SecurityHeaderScore:
    present: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    score: int = 0  # 0-100


@dataclass
class FingerprintResult:
    url: str
    final_url: str | None = None
    status_code: int | None = None
    technologies: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    security: SecurityHeaderScore = field(default_factory=SecurityHeaderScore)
    cdn: str | None = None
    ip: str | None = None
    error: str | None = None
    source: str = "http_fingerprint"


async def fingerprint_url(url: str) -> FingerprintResult:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    result = FingerprintResult(url=url)

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
            verify=False,
        ) as client:
            r = await client.get(url)
            result.final_url = str(r.url)
            result.status_code = r.status_code
            headers_lower = {k.lower(): v for k, v in r.headers.items()}
            result.headers = dict(headers_lower)

            # Detect technologies
            techs: set[str] = set()
            body_sample = r.text[:50000]
            for source, pattern, tech in _TECH_SIGNATURES:
                if source.startswith("header:"):
                    hname = source[7:]
                    hval = headers_lower.get(hname, "")
                    if hval and re.search(pattern, hval, re.IGNORECASE):
                        techs.add(tech)
                elif source == "body":
                    if re.search(pattern, body_sample, re.IGNORECASE):
                        techs.add(tech)
            result.technologies = sorted(techs)

            # CDN detection
            server = headers_lower.get("server", "").lower()
            via = headers_lower.get("via", "").lower()
            cf_ray = headers_lower.get("cf-ray", "")
            if cf_ray or "cloudflare" in server:
                result.cdn = "Cloudflare"
            elif "cloudfront" in server or "cloudfront" in via:
                result.cdn = "Amazon CloudFront"
            elif "fastly" in server or "fastly" in via:
                result.cdn = "Fastly"
            elif "akamai" in via:
                result.cdn = "Akamai"

            # Security headers scoring
            present = [h for h in _SECURITY_HEADERS if h in headers_lower]
            missing = [h for h in _SECURITY_HEADERS if h not in headers_lower]
            score = int(len(present) / len(_SECURITY_HEADERS) * 100)
            result.security = SecurityHeaderScore(present=present, missing=missing, score=score)

    except httpx.ConnectError:
        result.error = "Connection refused"
    except httpx.TimeoutException:
        result.error = "Timeout"
    except Exception as exc:
        result.error = str(exc)[:200]

    return result
