"""Subdomain takeover detection via crt.sh certificate transparency + DNS CNAME checks."""
from __future__ import annotations
import asyncio
import socket
from dataclasses import dataclass, field
import httpx

# CNAME targets known to be vulnerable to takeover when the DNS record exists
# but the service account/bucket/etc. has been deleted.
_VULNERABLE_CNAME_PATTERNS: list[tuple[str, str]] = [
    ("github.io", "GitHub Pages"),
    ("herokuapp.com", "Heroku"),
    ("s3.amazonaws.com", "AWS S3"),
    ("storage.googleapis.com", "Google Cloud Storage"),
    ("azurewebsites.net", "Azure Web Apps"),
    ("cloudapp.net", "Azure CloudApp"),
    ("trafficmanager.net", "Azure Traffic Manager"),
    ("blob.core.windows.net", "Azure Blob"),
    ("shopify.com", "Shopify"),
    ("fastly.net", "Fastly"),
    ("pantheonsite.io", "Pantheon"),
    ("wpengine.com", "WP Engine"),
    ("unbouncepages.com", "Unbounce"),
    ("hubspot.net", "HubSpot"),
    ("zendesk.com", "Zendesk"),
    ("netlify.app", "Netlify"),
    ("surge.sh", "Surge.sh"),
    ("webflow.io", "Webflow"),
    ("ghost.io", "Ghost"),
    ("cargo.site", "Cargo"),
]


@dataclass
class SubdomainResult:
    subdomain: str
    cname: str | None = None
    vulnerable_service: str | None = None
    risk: str = "low"  # low | medium | high | critical
    resolves: bool = True
    note: str | None = None


@dataclass
class SubdomainTakeoverReport:
    domain: str
    total_subdomains: int = 0
    vulnerable: list[SubdomainResult] = field(default_factory=list)
    safe: list[SubdomainResult] = field(default_factory=list)
    source: str = "crt.sh"


async def scan_domain(domain: str) -> SubdomainTakeoverReport:
    domain = domain.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
    report = SubdomainTakeoverReport(domain=domain)

    subdomains = await _fetch_subdomains_crtsh(domain)
    report.total_subdomains = len(subdomains)

    results = await asyncio.gather(*[_check_subdomain(s) for s in subdomains[:50]])
    for r in results:
        if r.vulnerable_service:
            report.vulnerable.append(r)
        else:
            report.safe.append(r)

    return report


async def _fetch_subdomains_crtsh(domain: str) -> list[str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{domain}", "output": "json"},
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                return []
            seen: set[str] = set()
            for entry in r.json():
                name = entry.get("name_value", "")
                for sub in name.split("\n"):
                    sub = sub.strip().lower()
                    if sub.endswith(f".{domain}") and sub not in seen:
                        seen.add(sub)
            return sorted(seen)
        except Exception:
            return []


async def _check_subdomain(subdomain: str) -> SubdomainResult:
    result = SubdomainResult(subdomain=subdomain)
    loop = asyncio.get_event_loop()

    try:
        # DNS CNAME lookup
        cname = await loop.run_in_executor(None, _get_cname, subdomain)
        if cname:
            result.cname = cname
            cname_lower = cname.lower()
            for pattern, service in _VULNERABLE_CNAME_PATTERNS:
                if pattern in cname_lower:
                    result.vulnerable_service = service
                    result.risk = "high"
                    result.note = f"CNAME points to {service} — verify the resource is still claimed."
                    break
    except Exception:
        result.resolves = False
        result.note = "No DNS resolution — may already be dangling."

    return result


def _get_cname(hostname: str) -> str | None:
    try:
        import dns.resolver  # type: ignore[import]
        answers = dns.resolver.resolve(hostname, "CNAME")
        return str(answers[0].target).rstrip(".")
    except Exception:
        pass
    # Fallback: socket can't resolve CNAME, just check resolution
    try:
        socket.gethostbyname(hostname)
    except socket.gaierror:
        raise
    return None
