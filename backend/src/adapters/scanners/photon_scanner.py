"""Photon scanner — web crawler that extracts OSINT data from a website."""

import asyncio
import re
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

try:
    from bs4 import BeautifulSoup  # type: ignore[import]
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False
    log.warning("beautifulsoup4 not installed; Photon scanner will have limited HTML parsing")

# Regexes
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{1,4}\)?[\s\-.]?\d{1,4}[\s\-.]?\d{1,9}"
)
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9]{48}"),           # OpenAI
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),           # GitHub personal access token
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),         # Google API key
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS access key
    re.compile(r"(?i)api[_\-]?key[\"'\s:=]+([A-Za-z0-9]{32,})"),
    re.compile(r"(?i)secret[\"'\s:=]+([A-Za-z0-9]{32,})"),
    re.compile(r"(?i)token[\"'\s:=]+([A-Za-z0-9]{32,})"),
    re.compile(r"[A-Za-z0-9]{40}"),               # Generic 40-char token (git-like)
]
_SOCIAL_DOMAINS = {
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "linkedin.com": "LinkedIn",
    "instagram.com": "Instagram",
    "github.com": "GitHub",
    "facebook.com": "Facebook",
    "youtube.com": "YouTube",
}

_MAX_DEPTH = 2
_MAX_PAGES = 50
_CRAWL_CONCURRENCY = 10
_CRAWL_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Photon/1.0)"}


class PhotonScanner(BaseOsintScanner):
    scanner_name = "photon"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Normalise URL
        if input_type == ScanInputType.DOMAIN and not input_value.startswith(("http://", "https://")):
            start_url = f"https://{input_value}"
        else:
            start_url = input_value

        parsed = urlparse(start_url)
        base_domain = parsed.netloc

        emails: set[str] = set()
        phones: set[str] = set()
        social_links: dict[str, list[str]] = {}
        external_domains: set[str] = set()
        js_secrets: list[str] = []
        meta_info: dict[str, Any] = {}
        pages_crawled = 0

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start_url, 0)])

        semaphore = asyncio.Semaphore(_CRAWL_CONCURRENCY)

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers=_CRAWL_HEADERS,
        ) as client:
            while queue and pages_crawled < _MAX_PAGES:
                batch = []
                while queue and len(batch) < _CRAWL_CONCURRENCY:
                    url, depth = queue.popleft()
                    if url in visited or depth > _MAX_DEPTH:
                        continue
                    visited.add(url)
                    batch.append((url, depth))

                if not batch:
                    break

                tasks = [
                    self._crawl_page(client, url, depth, semaphore)
                    for url, depth in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for (url, depth), result in zip(batch, results):
                    if isinstance(result, Exception):
                        log.debug("Crawl page failed", url=url, error=str(result))
                        continue

                    pages_crawled += 1
                    page_data: dict[str, Any] = result  # type: ignore[assignment]

                    emails.update(page_data.get("emails", []))
                    phones.update(page_data.get("phones", []))
                    js_secrets.extend(page_data.get("js_secrets", []))

                    for platform, links in page_data.get("social_links", {}).items():
                        social_links.setdefault(platform, [])
                        social_links[platform].extend(
                            l for l in links if l not in social_links[platform]
                        )

                    for ext_domain in page_data.get("external_domains", []):
                        if ext_domain != base_domain:
                            external_domains.add(ext_domain)

                    if not meta_info and page_data.get("meta_info"):
                        meta_info = page_data["meta_info"]

                    if depth < _MAX_DEPTH:
                        for link in page_data.get("internal_links", []):
                            if link not in visited:
                                queue.append((link, depth + 1))

        # Deduplicate js_secrets
        js_secrets = list(set(js_secrets))

        identifiers: list[str] = []
        identifiers.extend(f"email:{e}" for e in sorted(emails))
        identifiers.extend(f"phone:{p}" for p in sorted(phones))
        for links in social_links.values():
            identifiers.extend(f"url:{l}" for l in links)
        identifiers.extend(f"domain:{d}" for d in sorted(external_domains))

        return {
            "start_url": start_url,
            "emails": sorted(emails),
            "phones": sorted(phones),
            "social_links": {k: sorted(set(v)) for k, v in social_links.items()},
            "external_domains": sorted(external_domains),
            "js_secrets": js_secrets,
            "meta_info": meta_info,
            "pages_crawled": pages_crawled,
            "extracted_identifiers": identifiers,
        }

    async def _crawl_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        depth: int,
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        async with semaphore:
            resp = await client.get(url, timeout=10)

        content_type = resp.headers.get("content-type", "")
        text = resp.text

        emails: list[str] = _EMAIL_RE.findall(text)
        phones: list[str] = list({m.group() for m in _PHONE_RE.finditer(text) if len(m.group()) >= 7})
        js_secrets: list[str] = []

        # Extract secrets from JS files
        if "javascript" in content_type:
            for pattern in _SECRET_PATTERNS:
                for m in pattern.finditer(text):
                    secret = m.group()
                    if len(secret) >= 20:
                        js_secrets.append(secret)

        internal_links: list[str] = []
        external_domains: list[str] = []
        social_links: dict[str, list[str]] = {}
        meta_info: dict[str, Any] = {}
        forms: list[dict[str, Any]] = []

        if _BS4_AVAILABLE and "html" in content_type:
            soup = BeautifulSoup(text, "html.parser")
            parsed_base = urlparse(url)
            base_netloc = parsed_base.netloc

            # Collect links
            for tag in soup.find_all("a", href=True):
                href: str = tag["href"]
                abs_url = urljoin(url, href)
                parsed_link = urlparse(abs_url)
                if not parsed_link.scheme.startswith("http"):
                    continue
                if parsed_link.netloc == base_netloc:
                    internal_links.append(abs_url)
                else:
                    external_domains.append(parsed_link.netloc)
                    # Check for social links
                    for social_domain, platform in _SOCIAL_DOMAINS.items():
                        if social_domain in parsed_link.netloc:
                            social_links.setdefault(platform, [])
                            if abs_url not in social_links[platform]:
                                social_links[platform].append(abs_url)

            # Collect JS file secrets
            for script in soup.find_all("script", src=True):
                js_url = urljoin(url, script["src"])
                try:
                    js_resp = await client.get(js_url, timeout=8)
                    for pattern in _SECRET_PATTERNS:
                        for m in pattern.finditer(js_resp.text):
                            secret = m.group()
                            if len(secret) >= 20:
                                js_secrets.append(f"{js_url}: {secret}")
                except Exception:
                    pass

            # Meta tags
            for meta in soup.find_all("meta"):
                name = meta.get("name", meta.get("property", "")).lower()
                content = meta.get("content", "")
                if name in ("author", "generator", "keywords", "description") and content:
                    meta_info[name] = content

            # Forms
            for form in soup.find_all("form"):
                action = form.get("action", "")
                hidden_inputs = [
                    {"name": i.get("name", ""), "value": i.get("value", "")}
                    for i in form.find_all("input", type="hidden")
                ]
                forms.append({"action": action, "hidden_inputs": hidden_inputs})

        return {
            "url": url,
            "emails": emails,
            "phones": phones,
            "social_links": social_links,
            "internal_links": internal_links,
            "external_domains": external_domains,
            "js_secrets": js_secrets,
            "meta_info": meta_info,
            "forms": forms,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
