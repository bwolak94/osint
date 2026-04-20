"""Bio Link Extractor scanner — extract external links from social media bios.

Module 27 in the SOCMINT domain. Parses bio/description fields from publicly
accessible profiles to discover external pivoting points (personal sites, Linktree,
alternative social profiles, etc.).
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Regex pattern for URL extraction (simplified but robust)
URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>\)\]]+|"
    r"(?:www\.[a-zA-Z0-9][-a-zA-Z0-9.]{1,}\.[a-zA-Z]{2,}[^\s\"'<>\)\]]*)",
    re.IGNORECASE,
)


def _extract_urls(text: str) -> list[str]:
    """Extract URLs from text using regex."""
    found = URL_PATTERN.findall(text or "")
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for url in found:
        url = url.rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


class BioLinkExtractorScanner(BaseOsintScanner):
    """Extract external URLs from social media bios and profile descriptions.

    Checks Reddit About page and GitHub profile (both require no API key).
    Returns deduplicated list of discovered links for further pivoting.
    """

    scanner_name = "bio_link_extractor"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 7200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip().lstrip("@")
        discovered_links: list[dict[str, str]] = []
        bio_snippets: list[dict[str, str]] = []

        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "OSINT-Platform/1.0 BioLinkExtractor"},
            follow_redirects=True,
        ) as client:
            # --- Reddit ---
            try:
                resp = await client.get(f"https://www.reddit.com/user/{username}/about.json")
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    subreddit = data.get("subreddit", {})
                    bio_text = subreddit.get("public_description", "") or data.get("description", "")
                    if bio_text:
                        bio_snippets.append({"source": "reddit", "text": bio_text[:500]})
                        for url in _extract_urls(bio_text):
                            discovered_links.append({"source": "reddit_bio", "url": url})
            except Exception as exc:
                log.debug("bio_link_extractor: reddit fetch failed", error=str(exc))

            # --- GitHub ---
            try:
                resp = await client.get(
                    f"https://api.github.com/users/{username}",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    bio = data.get("bio") or ""
                    blog = data.get("blog") or ""
                    company = data.get("company") or ""
                    combined = f"{bio} {blog} {company}"
                    if combined.strip():
                        bio_snippets.append({"source": "github", "text": combined[:500]})
                    for url in _extract_urls(combined):
                        discovered_links.append({"source": "github_profile", "url": url})
                    # Blog field is often a direct URL
                    if blog and not blog.startswith("http"):
                        blog = f"https://{blog}"
                    if blog:
                        discovered_links.append({"source": "github_blog", "url": blog})
            except Exception as exc:
                log.debug("bio_link_extractor: github fetch failed", error=str(exc))

        # Deduplicate discovered_links by URL
        seen_urls: set[str] = set()
        unique_links: list[dict[str, str]] = []
        for link in discovered_links:
            if link["url"] not in seen_urls:
                seen_urls.add(link["url"])
                unique_links.append(link)

        found = len(unique_links) > 0
        return {
            "found": found,
            "username": username,
            "bio_snippets": bio_snippets,
            "discovered_links": unique_links,
            "total_links": len(unique_links),
            "extracted_identifiers": [f"url:{l['url']}" for l in unique_links],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
