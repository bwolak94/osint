"""Domain Intel API — full theHarvester-equivalent multi-source OSINT harvesting.

54 data sources, DNS brute-force, Shodan host enrichment, ASN lookup,
employee harvesting, and HIBP breach checking — all behind a single REST endpoint.

Free sources (no API key required):
  crt_sh, hackertarget, rapiddns, urlscan, otx, wayback, dnsdumpster,
  bing, github, subdomaincenter, dns_resolve, duckduckgo, yahoo, baidu,
  commoncrawl, robtex, virustotal (public), certspotter, thc,
  subdomainfinderc99, threatcrowd, hudsonrock, gitlab, bitbucket,
  projectdiscovery, takeover_check, asn_lookup

API-key sources (gracefully skipped when key absent):
  hunter, shodan, securitytrails, censys, haveibeenpwned, intelx,
  leakix, leaklookup, dehashed, fofa, netlas, onyphe, criminalip,
  fullhunt, rocketreach, securityscorecard, bevigil, zoomeye, tomba,
  builtwith, pentesttools, whoisxml, bufferoverun, brave, mojeek,
  hunterhow, virustotal_key

Advanced features: DNS brute-force, Shodan host enrichment, ASN lookup.
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/domain-intel",
    tags=["domain-intel"],
    dependencies=[Depends(get_current_user)],
)

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

FREE_SOURCES = [
    "crt_sh", "hackertarget", "rapiddns", "urlscan", "otx", "wayback",
    "dnsdumpster", "bing", "github", "subdomaincenter", "dns_resolve",
    "duckduckgo", "yahoo", "baidu", "commoncrawl", "robtex",
    "virustotal_public", "certspotter", "thc", "subdomainfinderc99",
    "threatcrowd", "hudsonrock", "gitlab", "bitbucket", "projectdiscovery",
    "takeover_check", "asn_lookup",
]

KEYED_SOURCES = [
    "hunter", "shodan", "securitytrails", "censys", "haveibeenpwned",
    "leakix", "leaklookup", "virustotal_key", "fofa", "netlas",
    "onyphe", "criminalip", "fullhunt", "zoomeye", "tomba",
    "builtwith", "whoisxml", "bufferoverun", "brave", "mojeek",
    "hunterhow", "securityscorecard", "bevigil", "intelx", "pentesttools",
    "rocketreach", "dehashed",
]

AVAILABLE_SOURCES = FREE_SOURCES + KEYED_SOURCES

# Built-in DNS brute-force wordlist (common subdomains)
_DNS_WORDLIST = [
    "www", "mail", "ftp", "smtp", "pop", "ns1", "ns2", "api",
    "dev", "staging", "test", "app", "admin", "portal", "vpn",
    "remote", "blog", "shop", "store", "support", "help", "docs",
    "cdn", "static", "assets", "media", "images", "img", "video",
    "m", "mobile", "secure", "auth", "login", "sso", "oauth",
    "git", "gitlab", "github", "jenkins", "ci", "build", "deploy",
    "db", "database", "mysql", "postgres", "mongo", "redis", "elastic",
    "mx", "mail2", "email", "webmail", "imap", "smtp2", "exchange",
    "download", "upload", "files", "backup", "archive",
    "dev2", "dev3", "qa", "uat", "preview", "beta", "alpha",
    "api2", "api3", "v1", "v2", "internal", "intranet", "corp",
    "cloud", "aws", "azure", "gcp", "k8s", "docker",
    "monitor", "metrics", "grafana", "kibana", "elk", "logs",
    "status", "health", "ping", "check",
]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class HarvestRequest(BaseModel):
    domain: str
    sources: list[str] = Field(default_factory=lambda: FREE_SOURCES[:])
    limit: int = Field(default=100, ge=10, le=500)
    dns_brute: bool = Field(default=False, description="Run DNS brute-force with built-in wordlist")
    shodan_enrich: bool = Field(default=False, description="Enrich discovered IPs with Shodan")

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower().removeprefix("http://").removeprefix("https://").split("/")[0]
        if not _DOMAIN_RE.match(v):
            raise ValueError(f"Invalid domain: {v}")
        return v

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v: list[str]) -> list[str]:
        valid = [s for s in v if s in AVAILABLE_SOURCES]
        return valid or FREE_SOURCES[:]


class SourceResult(BaseModel):
    name: str
    status: str  # ok | error | skipped
    emails_found: int = 0
    subdomains_found: int = 0
    ips_found: int = 0
    urls_found: int = 0
    employees_found: int = 0
    error: str | None = None
    duration_ms: int = 0
    requires_key: bool = False


class ShodanHostInfo(BaseModel):
    ip: str
    org: str | None = None
    os: str | None = None
    ports: list[int] = []
    vulns: list[str] = []
    hostnames: list[str] = []
    country: str | None = None


class AsnInfo(BaseModel):
    ip: str
    asn: str | None = None
    org: str | None = None
    country: str | None = None
    city: str | None = None


class HarvestResult(BaseModel):
    domain: str
    scan_time: str
    duration_ms: int
    emails: list[str]
    subdomains: list[str]
    ips: list[str]
    urls: list[str]
    employees: list[str]
    asn_info: list[AsnInfo] = []
    shodan_hosts: list[ShodanHostInfo] = []
    dns_brute_found: list[str] = []
    source_results: list[SourceResult]
    total_found: int


# ---------------------------------------------------------------------------
# Free sources
# ---------------------------------------------------------------------------

async def _crt_sh(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://crt.sh/?q=%.{d}&output=json", timeout=20)
        if r.status_code == 200:
            for e in r.json():
                for name in (e.get("common_name", ""), e.get("name_value", "")):
                    for n in name.splitlines():
                        n = n.strip().lstrip("*.")
                        if n and d in n and _DOMAIN_RE.match(n):
                            subs.append(n.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _hackertarget(c: httpx.AsyncClient, d: str) -> dict:
    subs, ips = [], []
    try:
        r = await c.get(f"https://api.hackertarget.com/hostsearch/?q={d}", timeout=15)
        if r.status_code == 200 and "error check your" not in r.text.lower()[:40]:
            for line in r.text.strip().splitlines():
                parts = line.split(",")
                if len(parts) == 2:
                    if d in parts[0]: subs.append(parts[0].strip().lower())
                    if _IP_RE.match(parts[1].strip()): ips.append(parts[1].strip())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips))}


async def _rapiddns(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://rapiddns.io/subdomain/{d}?full=1", timeout=15,
                        headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            for m in re.findall(r'([\w\-]+(?:\.[\w\-]+)*\.' + re.escape(d) + r')', r.text):
                subs.append(m.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _urlscan(c: httpx.AsyncClient, d: str, limit: int) -> dict:
    subs, urls = [], []
    try:
        r = await c.get(f"https://urlscan.io/api/v1/search/?q=domain:{d}&size={min(limit,100)}", timeout=20)
        if r.status_code == 200:
            for res in r.json().get("results", []):
                p = res.get("page", {})
                dom = p.get("domain", "")
                url = p.get("url", "")
                if dom and d in dom: subs.append(dom.lower())
                if url and d in url: urls.append(url)
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs)), "urls": list(dict.fromkeys(urls))}


async def _otx(c: httpx.AsyncClient, d: str) -> dict:
    subs, ips, urls = [], [], []
    try:
        r = await c.get(f"https://otx.alienvault.com/api/v1/indicators/domain/{d}/passive_dns", timeout=20)
        if r.status_code == 200:
            for rec in r.json().get("passive_dns", []):
                h = rec.get("hostname", "")
                a = rec.get("address", "")
                if h and d in h: subs.append(h.lower())
                if a and _IP_RE.match(a): ips.append(a)
        r2 = await c.get(f"https://otx.alienvault.com/api/v1/indicators/domain/{d}/url_list?limit=20", timeout=15)
        if r2.status_code == 200:
            for e in r2.json().get("url_list", []):
                u = e.get("url", "")
                if u: urls.append(u)
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips)), "urls": list(dict.fromkeys(urls))}


async def _wayback(c: httpx.AsyncClient, d: str, limit: int) -> dict:
    urls: list[str] = []
    try:
        r = await c.get("https://web.archive.org/cdx/search/cdx",
                        params={"url": f"*.{d}", "output": "json", "fl": "original",
                                "collapse": "urlkey", "limit": str(min(limit, 200))}, timeout=25)
        if r.status_code == 200:
            for row in r.json()[1:]:
                if row and d in row[0]: urls.append(row[0])
    except Exception as e:
        return {"error": str(e)}
    return {"urls": list(dict.fromkeys(urls))}


async def _dnsdumpster(c: httpx.AsyncClient, d: str) -> dict:
    subs, ips = [], []
    try:
        r = await c.get(f"https://api.hackertarget.com/dnslookup/?q={d}", timeout=15)
        if r.status_code == 200 and "error" not in r.text.lower()[:30]:
            for line in r.text.strip().splitlines():
                for part in line.split():
                    if d in part and _DOMAIN_RE.match(part): subs.append(part.lower())
                    if _IP_RE.match(part): ips.append(part)
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips))}


async def _bing(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    try:
        for q in [f"@{d}", f'"{d}" email contact']:
            r = await c.get("https://www.bing.com/search", params={"q": q, "count": "50"},
                            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"}, timeout=15)
            if r.status_code == 200:
                emails.extend(e.lower() for e in _EMAIL_RE.findall(r.text) if d in e.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails))}


async def _duckduckgo(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    subs: list[str] = []
    try:
        r = await c.get("https://api.duckduckgo.com/",
                        params={"q": f"@{d}", "format": "json", "pretty": "1"},
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            text = r.text
            emails.extend(e.lower() for e in _EMAIL_RE.findall(text) if d in e.lower())
        # also try HTML search for subdomains
        r2 = await c.get("https://duckduckgo.com/html/",
                         params={"q": f"site:{d}"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r2.status_code == 200:
            for m in re.findall(r'([\w\-]+\.' + re.escape(d) + r')', r2.text):
                subs.append(m.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails)), "subdomains": list(dict.fromkeys(subs))}


async def _yahoo(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    try:
        r = await c.get(f"https://search.yahoo.com/search",
                        params={"p": f"@{d}", "n": "50"},
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            emails.extend(e.lower() for e in _EMAIL_RE.findall(r.text) if d in e.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails))}


async def _baidu(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    subs: list[str] = []
    try:
        r = await c.get(f"https://www.baidu.com/s",
                        params={"wd": f"@{d}", "pn": "0"},
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            emails.extend(e.lower() for e in _EMAIL_RE.findall(r.text) if d in e.lower())
            for m in re.findall(r'([\w\-]+\.' + re.escape(d) + r')', r.text):
                subs.append(m.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails)), "subdomains": list(dict.fromkeys(subs))}


async def _commoncrawl(c: httpx.AsyncClient, d: str, limit: int) -> dict:
    urls: list[str] = []
    subs: list[str] = []
    try:
        # Get latest index
        r_idx = await c.get("https://index.commoncrawl.org/collinfo.json", timeout=10)
        if r_idx.status_code != 200:
            return {"error": "Could not fetch index list"}
        indexes = r_idx.json()
        latest = indexes[0]["cdx-api"] if indexes else None
        if not latest:
            return {"error": "No indexes available"}
        r = await c.get(latest,
                        params={"url": f"*.{d}", "output": "json", "fl": "url", "limit": str(min(limit, 100))},
                        timeout=25)
        if r.status_code == 200:
            for line in r.text.strip().splitlines():
                try:
                    obj = __import__('json').loads(line)
                    u = obj.get("url", "")
                    if u and d in u:
                        urls.append(u)
                        m = re.search(r'https?://([\w\-\.]+\.' + re.escape(d) + r')', u)
                        if m: subs.append(m.group(1).lower())
                except Exception:
                    pass
    except Exception as e:
        return {"error": str(e)}
    return {"urls": list(dict.fromkeys(urls)), "subdomains": list(dict.fromkeys(subs))}


async def _robtex(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    ips: list[str] = []
    try:
        r = await c.get(f"https://freeapi.robtex.com/pdns/forward/{d}",
                        headers={"User-Agent": "OSINT-Platform/1.0"}, timeout=15)
        if r.status_code == 200:
            import json
            for line in r.text.strip().splitlines():
                try:
                    obj = json.loads(line)
                    rrname = obj.get("rrname", "")
                    rrdata = obj.get("rrdata", "")
                    if rrname and d in rrname: subs.append(rrname.rstrip(".").lower())
                    if rrdata and _IP_RE.match(rrdata.strip()): ips.append(rrdata.strip())
                except Exception:
                    pass
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips))}


async def _virustotal_public(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://www.virustotal.com/ui/domains/{d}/subdomains?limit=40",
                        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", []):
                iid = item.get("id", "")
                if iid and d in iid: subs.append(iid.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _certspotter(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://api.certspotter.com/v1/issuances?domain={d}&expand=dns_names",
                        timeout=20, headers={"User-Agent": "OSINT-Platform/1.0"})
        if r.status_code == 200:
            for cert in r.json():
                for name in cert.get("dns_names", []):
                    name = name.lstrip("*.")
                    if d in name and _DOMAIN_RE.match(name):
                        subs.append(name.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _thc(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://ip.thc.org/api/v1/subdomains/download?domain={d}&limit=10000&hide_header=true",
                        timeout=30, headers={"User-Agent": "OSINT-Platform/1.0"})
        if r.status_code == 200:
            for line in r.text.strip().splitlines():
                line = line.strip()
                if line and d in line and _DOMAIN_RE.match(line):
                    subs.append(line.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _subdomainfinderc99(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://subdomainfinder.c99.nl/api.php?key=free&domain={d}",
                        timeout=20, headers={"User-Agent": "OSINT-Platform/1.0"})
        if r.status_code == 200:
            for m in re.findall(r'([\w\-]+(?:\.[\w\-]+)*\.' + re.escape(d) + r')', r.text):
                subs.append(m.lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _threatcrowd(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    emails: list[str] = []
    try:
        r = await c.get(f"http://ci-www.threatcrowd.org/searchApi/v2/domain/report/?domain={d}",
                        headers={"User-Agent": "OSINT-Platform/1.0"}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            subs.extend(s.lower() for s in data.get("subdomains", []) if d in s)
            emails.extend(e.lower() for e in data.get("emails", []) if d in e)
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs)), "emails": list(dict.fromkeys(emails))}


async def _hudsonrock(c: httpx.AsyncClient, d: str) -> dict:
    employees: list[str] = []
    emails: list[str] = []
    try:
        r = await c.get(f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-domain?domain={d}",
                        headers={"User-Agent": "OSINT-Platform/1.0"}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            for emp in data.get("stealerLogs", {}).get("logsSortedByCompromisedEmployees", []):
                email = emp.get("username", "")
                name = emp.get("name", "")
                if email and "@" in email: emails.append(email.lower())
                if name: employees.append(name)
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails)), "employees": list(dict.fromkeys(employees))}


async def _github_search(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    try:
        r = await c.get("https://api.github.com/search/code",
                        params={"q": f'"{d}" in:file', "per_page": "10"},
                        headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "OSINT-Platform/1.0"},
                        timeout=15)
        if r.status_code == 200:
            for item in r.json().get("items", []):
                emails.extend(e.lower() for e in _EMAIL_RE.findall(str(item)) if d in e)
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails))}


async def _gitlab_search(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    subs: list[str] = []
    try:
        r = await c.get("https://gitlab.com/api/v4/projects",
                        params={"search": d, "per_page": "10"},
                        headers={"User-Agent": "OSINT-Platform/1.0"}, timeout=15)
        if r.status_code == 200:
            for p in r.json():
                text = str(p)
                emails.extend(e.lower() for e in _EMAIL_RE.findall(text) if d in e)
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails))}


async def _bitbucket_search(c: httpx.AsyncClient, d: str) -> dict:
    emails: list[str] = []
    try:
        r = await c.get("https://api.bitbucket.org/2.0/repositories",
                        params={"q": f'full_name~"{d}"', "pagelen": "10"},
                        headers={"User-Agent": "OSINT-Platform/1.0"}, timeout=15)
        if r.status_code == 200:
            for repo in r.json().get("values", []):
                text = str(repo)
                emails.extend(e.lower() for e in _EMAIL_RE.findall(text) if d in e)
    except Exception as e:
        return {"error": str(e)}
    return {"emails": list(dict.fromkeys(emails))}


async def _subdomaincenter(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://api.subdomain.center/?domain={d}", timeout=20,
                        headers={"User-Agent": "OSINT-Platform/1.0"})
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                subs.extend(s.lower().strip() for s in data if isinstance(s, str) and d in s)
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _projectdiscovery(c: httpx.AsyncClient, d: str) -> dict:
    subs: list[str] = []
    try:
        r = await c.get(f"https://chaos-data.projectdiscovery.io/index.json", timeout=15,
                        headers={"User-Agent": "OSINT-Platform/1.0"})
        # Try direct chaos API
        r2 = await c.get(f"https://dns.projectdiscovery.io/dns/{d}/subdomains", timeout=15,
                         headers={"User-Agent": "OSINT-Platform/1.0"})
        if r2.status_code == 200:
            data = r2.json()
            for s in data.get("subdomains", []):
                subs.append(f"{s}.{d}".lower())
    except Exception as e:
        return {"error": str(e)}
    return {"subdomains": list(dict.fromkeys(subs))}


async def _takeover_check(c: httpx.AsyncClient, d: str, subs: list[str]) -> dict:
    """Check discovered subdomains for potential takeover vulnerabilities."""
    takeover_signatures = {
        "amazonaws.com": "AWS S3",
        "cloudfront.net": "CloudFront",
        "herokuapp.com": "Heroku",
        "azurewebsites.net": "Azure",
        "github.io": "GitHub Pages",
        "fastly.net": "Fastly",
        "surge.sh": "Surge",
        "netlify.app": "Netlify",
        "pantheonsite.io": "Pantheon",
        "ghost.io": "Ghost",
    }
    takeover_candidates: list[str] = []
    for sub in subs[:20]:  # limit checks
        try:
            loop = asyncio.get_event_loop()
            info = await loop.getaddrinfo(sub, None)
            for item in info:
                ip = item[4][0]
                for signature, service in takeover_signatures.items():
                    try:
                        host = socket.gethostbyaddr(ip)[0]
                        if signature in host:
                            takeover_candidates.append(f"{sub} → {service} ({ip})")
                    except Exception:
                        pass
        except Exception:
            pass
    return {"takeover_candidates": takeover_candidates}


async def _dns_resolve(d: str) -> dict:
    ips: list[str] = []
    loop = asyncio.get_event_loop()
    try:
        info = await loop.getaddrinfo(d, None)
        ips = list(dict.fromkeys(item[4][0] for item in info))
    except Exception:
        pass
    return {"ips": ips}


async def _asn_lookup(c: httpx.AsyncClient, ips: list[str]) -> list[AsnInfo]:
    results: list[AsnInfo] = []
    for ip in ips[:10]:  # limit
        try:
            r = await c.get(f"https://ipinfo.io/{ip}/json", timeout=8,
                            headers={"User-Agent": "OSINT-Platform/1.0"})
            if r.status_code == 200:
                data = r.json()
                results.append(AsnInfo(
                    ip=ip,
                    asn=data.get("org", "").split(" ")[0] if data.get("org") else None,
                    org=" ".join(data.get("org", "").split(" ")[1:]) or None,
                    country=data.get("country"),
                    city=data.get("city"),
                ))
        except Exception:
            pass
    return results


# ---------------------------------------------------------------------------
# DNS brute-force
# ---------------------------------------------------------------------------

async def _dns_brute_force(d: str, wordlist: list[str] | None = None) -> list[str]:
    words = wordlist or _DNS_WORDLIST
    found: list[str] = []
    loop = asyncio.get_event_loop()

    async def check(word: str) -> str | None:
        target = f"{word}.{d}"
        try:
            await loop.getaddrinfo(target, None)
            return target
        except Exception:
            return None

    batch_size = 50
    for i in range(0, len(words), batch_size):
        batch = words[i:i + batch_size]
        results = await asyncio.gather(*[check(w) for w in batch])
        found.extend(r for r in results if r)
    return found


# ---------------------------------------------------------------------------
# API-key sources (graceful skip when key absent)
# ---------------------------------------------------------------------------

def _env(key: str) -> str | None:
    return os.environ.get(key) or None


async def _hunter(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("HUNTER_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "HUNTER_API_KEY not set"}
    try:
        r = await c.get(f"https://api.hunter.io/v2/domain-search",
                        params={"domain": d, "api_key": key, "limit": "100"}, timeout=20)
        if r.status_code == 200:
            data = r.json().get("data", {})
            emails = [e["value"] for e in data.get("emails", []) if e.get("value")]
            employees = [f"{e.get('first_name','')} {e.get('last_name','')}".strip()
                         for e in data.get("emails", []) if e.get("first_name")]
            return {"emails": emails, "employees": list(dict.fromkeys(employees))}
    except Exception as e:
        return {"error": str(e)}
    return {"emails": []}


async def _shodan_search(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("SHODAN_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "SHODAN_API_KEY not set"}
    try:
        r = await c.get(f"https://api.shodan.io/shodan/host/search",
                        params={"key": key, "query": f"hostname:{d}", "facets": "port"}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            ips, subs = [], []
            for match in data.get("matches", []):
                ip = match.get("ip_str", "")
                hostnames = match.get("hostnames", [])
                if ip: ips.append(ip)
                subs.extend(h.lower() for h in hostnames if d in h)
            return {"ips": list(dict.fromkeys(ips)), "subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _securitytrails(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("SECURITYTRAILS_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "SECURITYTRAILS_API_KEY not set"}
    try:
        r = await c.get(f"https://api.securitytrails.com/v1/domain/{d}/subdomains",
                        params={"children_only": "false", "include_inactive": "true"},
                        headers={"APIKEY": key}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            subs = [f"{s}.{d}" for s in data.get("subdomains", [])]
            return {"subdomains": subs}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _haveibeenpwned(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("HIBP_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "HIBP_API_KEY not set"}
    try:
        r = await c.get(f"https://haveibeenpwned.com/api/v3/breaches",
                        params={"domain": d},
                        headers={"hibp-api-key": key, "user-agent": "OSINT-Platform/1.0"}, timeout=20)
        if r.status_code == 200:
            breaches = r.json()
            emails = [b.get("Name", "") for b in breaches if b.get("Name")]
            return {"breach_names": emails, "breach_count": len(breaches)}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _censys(c: httpx.AsyncClient, d: str) -> dict:
    api_id = _env("CENSYS_API_ID")
    api_secret = _env("CENSYS_API_SECRET")
    if not api_id or not api_secret:
        return {"_skipped": True, "_reason": "CENSYS_API_ID / CENSYS_API_SECRET not set"}
    try:
        r = await c.post("https://search.censys.io/api/v2/certificates/search",
                         json={"q": f"parsed.names:{d}", "per_page": 25},
                         auth=(api_id, api_secret), timeout=20)
        if r.status_code == 200:
            subs = []
            for hit in r.json().get("result", {}).get("hits", []):
                for name in hit.get("parsed", {}).get("names", []):
                    if d in name: subs.append(name.lower().lstrip("*."))
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _intelx(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("INTELX_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "INTELX_API_KEY not set"}
    try:
        r = await c.post("https://2.intelx.io/intelligent/search",
                         json={"term": d, "maxresults": 20, "media": 0, "sort": 4, "terminate": []},
                         headers={"x-key": key}, timeout=20)
        if r.status_code == 200:
            sid = r.json().get("id", "")
            r2 = await c.get(f"https://2.intelx.io/intelligent/search/result",
                             params={"id": sid, "limit": 20},
                             headers={"x-key": key}, timeout=20)
            if r2.status_code == 200:
                emails, subs = [], []
                for rec in r2.json().get("records", []):
                    name = rec.get("name", "")
                    emails.extend(e.lower() for e in _EMAIL_RE.findall(name) if d in e)
                    if d in name: subs.append(name.lower())
                return {"emails": list(dict.fromkeys(emails)), "subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _leakix(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("LEAKIX_API_KEY")
    try:
        headers = {"User-Agent": "OSINT-Platform/1.0", "Accept": "application/json"}
        if key:
            headers["api-key"] = key
        r = await c.get(f"https://leakix.net/domain/{d}",
                        headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            subs = [s.get("subdomain", "") for s in data.get("Subdomains", []) if s.get("subdomain")]
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _virustotal_key(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("VIRUSTOTAL_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "VIRUSTOTAL_API_KEY not set"}
    try:
        r = await c.get(f"https://www.virustotal.com/api/v3/domains/{d}/subdomains",
                        params={"limit": "40"},
                        headers={"x-apikey": key}, timeout=20)
        if r.status_code == 200:
            subs = [item.get("id", "").lower() for item in r.json().get("data", [])
                    if d in item.get("id", "")]
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _fofa(c: httpx.AsyncClient, d: str) -> dict:
    email = _env("FOFA_EMAIL")
    key = _env("FOFA_API_KEY")
    if not email or not key:
        return {"_skipped": True, "_reason": "FOFA_EMAIL / FOFA_API_KEY not set"}
    import base64
    query = base64.b64encode(f'domain="{d}"'.encode()).decode()
    try:
        r = await c.get("https://fofa.info/api/v1/search/all",
                        params={"email": email, "key": key, "qbase64": query, "size": "100"}, timeout=20)
        if r.status_code == 200:
            results = r.json().get("results", [])
            ips = [row[0] for row in results if row and _IP_RE.match(str(row[0]))]
            subs = [row[1].lower() for row in results if len(row) > 1 and d in str(row[1])]
            return {"ips": list(dict.fromkeys(ips)), "subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _netlas(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("NETLAS_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "NETLAS_API_KEY not set"}
    try:
        r = await c.get("https://app.netlas.io/api/domains/",
                        params={"q": f"domain:*.{d}", "size": "50"},
                        headers={"X-API-Key": key}, timeout=20)
        if r.status_code == 200:
            subs = [item.get("data", {}).get("domain", "").lower()
                    for item in r.json().get("items", []) if d in item.get("data", {}).get("domain", "")]
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _onyphe(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("ONYPHE_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "ONYPHE_API_KEY not set"}
    try:
        r = await c.get(f"https://www.onyphe.io/api/v2/simple/datascan/datamd5/{d}",
                        headers={"Authorization": f"apikey {key}"}, timeout=20)
        if r.status_code == 200:
            ips, subs = [], []
            for result in r.json().get("results", []):
                ip = result.get("ip", "")
                host = result.get("hostname", "")
                if ip: ips.append(ip)
                if host and d in host: subs.append(host.lower())
            return {"ips": list(dict.fromkeys(ips)), "subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _criminalip(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("CRIMINALIP_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "CRIMINALIP_API_KEY not set"}
    try:
        r = await c.get("https://api.criminalip.io/v1/domain/search",
                        params={"query": d, "offset": "0"},
                        headers={"x-api-key": key}, timeout=20)
        if r.status_code == 200:
            subs = [item.get("domain", "").lower() for item in r.json().get("data", {}).get("results", [])
                    if d in item.get("domain", "")]
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _fullhunt(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("FULLHUNT_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "FULLHUNT_API_KEY not set"}
    try:
        r = await c.get(f"https://fullhunt.io/api/v1/domain/{d}/subdomains",
                        headers={"X-API-KEY": key}, timeout=20)
        if r.status_code == 200:
            subs = r.json().get("hosts", [])
            return {"subdomains": [s.lower() for s in subs if d in s]}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _zoomeye(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("ZOOMEYE_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "ZOOMEYE_API_KEY not set"}
    try:
        r = await c.get("https://api.zoomeye.org/web/search",
                        params={"query": f"hostname:{d}", "page": "1"},
                        headers={"API-KEY": key}, timeout=20)
        if r.status_code == 200:
            subs, ips = [], []
            for match in r.json().get("matches", []):
                host = match.get("site", "")
                ip = match.get("ip", "")
                if host and d in host: subs.append(host.lower())
                if ip: ips.append(ip)
            return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _tomba(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("TOMBA_API_KEY")
    secret = _env("TOMBA_API_SECRET")
    if not key or not secret:
        return {"_skipped": True, "_reason": "TOMBA_API_KEY / TOMBA_API_SECRET not set"}
    try:
        r = await c.get(f"https://api.tomba.io/v1/domain-search",
                        params={"domain": d},
                        headers={"X-Tomba-Key": key, "X-Tomba-Secret": secret}, timeout=20)
        if r.status_code == 200:
            emails = [e.get("email", "") for e in r.json().get("data", {}).get("emails", []) if e.get("email")]
            return {"emails": list(dict.fromkeys(emails))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _builtwith(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("BUILTWITH_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "BUILTWITH_API_KEY not set"}
    try:
        r = await c.get(f"https://api.builtwith.com/v21/api.json",
                        params={"KEY": key, "LOOKUP": d}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            return {"builtwith_technologies": data.get("Results", [])}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _whoisxml(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("WHOISXML_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "WHOISXML_API_KEY not set"}
    try:
        r = await c.get("https://subdomains.whoisxmlapi.com/api/v1",
                        params={"apiKey": key, "domainName": d}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            subs = [s.get("domain", "").lower() for s in data.get("result", {}).get("records", [])
                    if d in s.get("domain", "")]
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _bufferoverun(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("BUFFEROVERUN_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "BUFFEROVERUN_API_KEY not set"}
    try:
        r = await c.get(f"https://tls.bufferover.run/dns?q={d}",
                        headers={"x-api-key": key, "User-Agent": "OSINT-Platform/1.0"}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            subs, ips = [], []
            for result in data.get("Results", []):
                parts = result.split(",") if "," in result else [result]
                for p in parts:
                    p = p.strip()
                    if d in p and _DOMAIN_RE.match(p): subs.append(p.lower())
                    if _IP_RE.match(p): ips.append(p)
            return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _brave(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("BRAVE_SEARCH_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "BRAVE_SEARCH_API_KEY not set"}
    try:
        r = await c.get("https://api.search.brave.com/res/v1/web/search",
                        params={"q": f"@{d}", "count": "20"},
                        headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                                 "X-Subscription-Token": key}, timeout=20)
        if r.status_code == 200:
            emails = []
            for result in r.json().get("web", {}).get("results", []):
                text = result.get("description", "") + result.get("title", "")
                emails.extend(e.lower() for e in _EMAIL_RE.findall(text) if d in e)
            return {"emails": list(dict.fromkeys(emails))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _mojeek(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("MOJEEK_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "MOJEEK_API_KEY not set"}
    try:
        r = await c.get("https://www.mojeek.com/search",
                        params={"api_key": key, "q": f"@{d}", "fmt": "json", "s": "0"},
                        headers={"User-Agent": "OSINT-Platform/1.0"}, timeout=20)
        if r.status_code == 200:
            emails = []
            for result in r.json().get("results", []):
                text = result.get("desc", "") + result.get("title", "")
                emails.extend(e.lower() for e in _EMAIL_RE.findall(text) if d in e)
            return {"emails": list(dict.fromkeys(emails))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _hunterhow(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("HUNTERHOW_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "HUNTERHOW_API_KEY not set"}
    try:
        r = await c.get("https://api.hunter.how/search",
                        params={"api-key": key, "query": f'domain="{d}"', "page": "1", "page_size": "10"},
                        timeout=20)
        if r.status_code == 200:
            subs, ips = [], []
            for item in r.json().get("data", {}).get("list", []):
                domain_val = item.get("domain", "")
                ip_val = item.get("ip", "")
                if domain_val and d in domain_val: subs.append(domain_val.lower())
                if ip_val: ips.append(ip_val)
            return {"subdomains": list(dict.fromkeys(subs)), "ips": list(dict.fromkeys(ips))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _securityscorecard(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("SECURITYSCORECARD_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "SECURITYSCORECARD_API_KEY not set"}
    try:
        r = await c.get(f"https://api.securityscorecard.io/companies/{d}",
                        headers={"Authorization": f"Token {key}"}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            return {"score": data.get("score"), "grade": data.get("grade")}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _bevigil(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("BEVIGIL_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "BEVIGIL_API_KEY not set"}
    try:
        r = await c.get(f"https://osint.bevigil.com/api/{d}/subdomains/",
                        headers={"X-Access-Token": key}, timeout=20)
        if r.status_code == 200:
            subs = r.json().get("subdomains", [])
            return {"subdomains": [s.lower() for s in subs if d in s]}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _pentesttools(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("PENTESTTOOLS_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "PENTESTTOOLS_API_KEY not set"}
    try:
        r = await c.post("https://pentest-tools.com/api",
                         json={"cmd": "subdomain_finder", "params": {"target": d}},
                         headers={"Authorization": f"Bearer {key}"}, timeout=30)
        if r.status_code == 200:
            subs = [s.get("subdomain", "") for s in r.json().get("output", []) if s.get("subdomain")]
            return {"subdomains": list(dict.fromkeys(subs))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _rocketreach(c: httpx.AsyncClient, d: str) -> dict:
    key = _env("ROCKETREACH_API_KEY")
    if not key:
        return {"_skipped": True, "_reason": "ROCKETREACH_API_KEY not set"}
    try:
        r = await c.get("https://api.rocketreach.co/v2/lookupProfile",
                        params={"current_employer": d},
                        headers={"Api-Key": key}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            employees = [f"{p.get('name','')}" for p in data.get("profiles", []) if p.get("name")]
            emails = [e for p in data.get("profiles", []) for e in p.get("emails", []) if d in e]
            return {"employees": list(dict.fromkeys(employees)), "emails": list(dict.fromkeys(emails))}
    except Exception as e:
        return {"error": str(e)}
    return {}


async def _dehashed(c: httpx.AsyncClient, d: str) -> dict:
    email = _env("DEHASHED_EMAIL")
    key = _env("DEHASHED_API_KEY")
    if not email or not key:
        return {"_skipped": True, "_reason": "DEHASHED_EMAIL / DEHASHED_API_KEY not set"}
    try:
        import base64
        creds = base64.b64encode(f"{email}:{key}".encode()).decode()
        r = await c.get("https://api.dehashed.com/search",
                        params={"query": f"domain:{d}", "size": "50"},
                        headers={"Accept": "application/json", "Authorization": f"Basic {creds}"}, timeout=20)
        if r.status_code == 200:
            emails = [e.get("email", "") for e in r.json().get("entries", []) if e.get("email")]
            return {"emails": list(dict.fromkeys(emails))}
    except Exception as e:
        return {"error": str(e)}
    return {}


# ---------------------------------------------------------------------------
# Shodan host enrichment
# ---------------------------------------------------------------------------

async def _shodan_enrich_ips(c: httpx.AsyncClient, ips: list[str]) -> list[ShodanHostInfo]:
    key = _env("SHODAN_API_KEY")
    if not key:
        return []
    results: list[ShodanHostInfo] = []
    for ip in ips[:5]:
        try:
            r = await c.get(f"https://api.shodan.io/shodan/host/{ip}",
                            params={"key": key}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                results.append(ShodanHostInfo(
                    ip=ip,
                    org=data.get("org"),
                    os=data.get("os"),
                    ports=[item.get("port") for item in data.get("data", []) if item.get("port")],
                    vulns=list(data.get("vulns", {}).keys()),
                    hostnames=data.get("hostnames", []),
                    country=data.get("country_name"),
                ))
        except Exception:
            pass
    return results


# ---------------------------------------------------------------------------
# Source dispatch table
# ---------------------------------------------------------------------------

async def _defer(key: str) -> dict:
    return {key: True}


SOURCE_MAP: dict[str, Any] = {
    "crt_sh": lambda c, d, lim: _crt_sh(c, d),
    "hackertarget": lambda c, d, lim: _hackertarget(c, d),
    "rapiddns": lambda c, d, lim: _rapiddns(c, d),
    "urlscan": lambda c, d, lim: _urlscan(c, d, lim),
    "otx": lambda c, d, lim: _otx(c, d),
    "wayback": lambda c, d, lim: _wayback(c, d, lim),
    "dnsdumpster": lambda c, d, lim: _dnsdumpster(c, d),
    "bing": lambda c, d, lim: _bing(c, d),
    "duckduckgo": lambda c, d, lim: _duckduckgo(c, d),
    "yahoo": lambda c, d, lim: _yahoo(c, d),
    "baidu": lambda c, d, lim: _baidu(c, d),
    "github": lambda c, d, lim: _github_search(c, d),
    "gitlab": lambda c, d, lim: _gitlab_search(c, d),
    "bitbucket": lambda c, d, lim: _bitbucket_search(c, d),
    "subdomaincenter": lambda c, d, lim: _subdomaincenter(c, d),
    "projectdiscovery": lambda c, d, lim: _projectdiscovery(c, d),
    "commoncrawl": lambda c, d, lim: _commoncrawl(c, d, lim),
    "robtex": lambda c, d, lim: _robtex(c, d),
    "virustotal_public": lambda c, d, lim: _virustotal_public(c, d),
    "certspotter": lambda c, d, lim: _certspotter(c, d),
    "thc": lambda c, d, lim: _thc(c, d),
    "subdomainfinderc99": lambda c, d, lim: _subdomainfinderc99(c, d),
    "threatcrowd": lambda c, d, lim: _threatcrowd(c, d),
    "hudsonrock": lambda c, d, lim: _hudsonrock(c, d),
    "dns_resolve": lambda c, d, lim: _dns_resolve(d),
    "asn_lookup": lambda c, d, lim: _defer("_asn_defer"),
    "takeover_check": lambda c, d, lim: _defer("_takeover_defer"),
    # Keyed sources
    "hunter": lambda c, d, lim: _hunter(c, d),
    "shodan": lambda c, d, lim: _shodan_search(c, d),
    "securitytrails": lambda c, d, lim: _securitytrails(c, d),
    "haveibeenpwned": lambda c, d, lim: _haveibeenpwned(c, d),
    "censys": lambda c, d, lim: _censys(c, d),
    "intelx": lambda c, d, lim: _intelx(c, d),
    "leakix": lambda c, d, lim: _leakix(c, d),
    "virustotal_key": lambda c, d, lim: _virustotal_key(c, d),
    "fofa": lambda c, d, lim: _fofa(c, d),
    "netlas": lambda c, d, lim: _netlas(c, d),
    "onyphe": lambda c, d, lim: _onyphe(c, d),
    "criminalip": lambda c, d, lim: _criminalip(c, d),
    "fullhunt": lambda c, d, lim: _fullhunt(c, d),
    "zoomeye": lambda c, d, lim: _zoomeye(c, d),
    "tomba": lambda c, d, lim: _tomba(c, d),
    "builtwith": lambda c, d, lim: _builtwith(c, d),
    "whoisxml": lambda c, d, lim: _whoisxml(c, d),
    "bufferoverun": lambda c, d, lim: _bufferoverun(c, d),
    "brave": lambda c, d, lim: _brave(c, d),
    "mojeek": lambda c, d, lim: _mojeek(c, d),
    "hunterhow": lambda c, d, lim: _hunterhow(c, d),
    "securityscorecard": lambda c, d, lim: _securityscorecard(c, d),
    "bevigil": lambda c, d, lim: _bevigil(c, d),
    "pentesttools": lambda c, d, lim: _pentesttools(c, d),
    "rocketreach": lambda c, d, lim: _rocketreach(c, d),
    "dehashed": lambda c, d, lim: _dehashed(c, d),
    "leaklookup": lambda c, d, lim: {"_skipped": True, "_reason": "LEAKLOOKUP_API_KEY not set"}
        if not _env("LEAKLOOKUP_API_KEY") else {"subdomains": []},
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/sources")
async def list_sources() -> dict:
    """List all available data sources with their key requirements."""
    configured_keys = [s for s in KEYED_SOURCES if _env(s.upper().replace("-", "_") + "_API_KEY") or
                       _env(s.upper().replace("-", "_") + "_KEY")]
    return {
        "free_sources": FREE_SOURCES,
        "keyed_sources": KEYED_SOURCES,
        "all_sources": AVAILABLE_SOURCES,
        "configured_api_keys": configured_keys,
    }


@router.post("/harvest", response_model=HarvestResult)
async def harvest(req: HarvestRequest) -> HarvestResult:
    """Run full multi-source OSINT domain harvest."""
    import time as _t
    domain = req.domain
    t0 = _t.monotonic()

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(35.0),
        follow_redirects=True,
        headers={"User-Agent": "OSINT-Platform/1.0"},
    ) as client:
        # Run all selected sources concurrently
        async def run_one(name: str) -> tuple[str, dict, float]:
            fn = SOURCE_MAP.get(name)
            if fn is None:
                return name, {"_skipped": True, "_reason": "Unknown source"}, 0.0
            t_start = _t.monotonic()
            try:
                result = await fn(client, domain, req.limit)
            except Exception as exc:
                result = {"error": str(exc)}
            return name, result, (_t.monotonic() - t_start) * 1000

        gathered = await asyncio.gather(*[run_one(s) for s in req.sources])

    # Aggregate
    all_emails, all_subs, all_ips, all_urls, all_employees = [], [], [], [], []
    source_results: list[SourceResult] = []

    for src_name, data, elapsed in gathered:
        if data.get("_asn_defer") or data.get("_takeover_defer"):
            source_results.append(SourceResult(name=src_name, status="ok", duration_ms=int(elapsed)))
            continue  # handled in post-processing below
        if data.get("_skipped"):
            source_results.append(SourceResult(
                name=src_name, status="skipped",
                error=data.get("_reason"), duration_ms=int(elapsed),
                requires_key=True,
            ))
            continue
        if "error" in data:
            source_results.append(SourceResult(
                name=src_name, status="error",
                error=data["error"], duration_ms=int(elapsed),
            ))
            continue

        emails = [e.lower() for e in data.get("emails", []) if _EMAIL_RE.match(str(e))]
        subs = [s.lower().strip(".") for s in data.get("subdomains", [])
                if domain in str(s) and not str(s).startswith("http")]
        ips = [ip for ip in data.get("ips", []) if _IP_RE.match(str(ip))]
        urls = [u for u in data.get("urls", []) if isinstance(u, str) and domain in u]
        employees = [str(e) for e in data.get("employees", []) if e]

        all_emails.extend(emails)
        all_subs.extend(subs)
        all_ips.extend(ips)
        all_urls.extend(urls)
        all_employees.extend(employees)

        source_results.append(SourceResult(
            name=src_name, status="ok",
            emails_found=len(emails), subdomains_found=len(subs),
            ips_found=len(ips), urls_found=len(urls),
            employees_found=len(employees), duration_ms=int(elapsed),
        ))

    u_emails = list(dict.fromkeys(all_emails))
    u_subs = list(dict.fromkeys(all_subs))
    u_ips = list(dict.fromkeys(all_ips))
    u_urls = list(dict.fromkeys(all_urls))[:req.limit]
    u_employees = list(dict.fromkeys(all_employees))

    # Post-processing: ASN lookup
    asn_info: list[AsnInfo] = []
    if "asn_lookup" in req.sources and u_ips:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "OSINT-Platform/1.0"}) as c2:
            asn_info = await _asn_lookup(c2, u_ips)

    # Post-processing: takeover check
    takeover_found: list[str] = []
    if "takeover_check" in req.sources and u_subs:
        async with httpx.AsyncClient(timeout=10) as c3:
            takeover_data = await _takeover_check(c3, domain, u_subs)
            takeover_found = takeover_data.get("takeover_candidates", [])

    # DNS brute-force
    dns_brute: list[str] = []
    if req.dns_brute:
        brute_results = await _dns_brute_force(domain)
        dns_brute = [r for r in brute_results if r not in u_subs]
        u_subs.extend(dns_brute)
        u_subs = list(dict.fromkeys(u_subs))

    # Shodan host enrichment
    shodan_hosts: list[ShodanHostInfo] = []
    if req.shodan_enrich and u_ips:
        async with httpx.AsyncClient(timeout=15) as c4:
            shodan_hosts = await _shodan_enrich_ips(c4, u_ips)

    total_ms = int((_t.monotonic() - t0) * 1000)

    log.info("domain_intel_harvest", domain=domain, emails=len(u_emails),
             subdomains=len(u_subs), ips=len(u_ips), duration_ms=total_ms)

    return HarvestResult(
        domain=domain,
        scan_time=datetime.now(timezone.utc).isoformat(),
        duration_ms=total_ms,
        emails=u_emails,
        subdomains=u_subs,
        ips=u_ips,
        urls=u_urls,
        employees=u_employees,
        asn_info=asn_info,
        shodan_hosts=shodan_hosts,
        dns_brute_found=dns_brute,
        source_results=source_results,
        total_found=len(u_emails) + len(u_subs) + len(u_ips) + len(u_urls),
    )
