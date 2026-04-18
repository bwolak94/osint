"""LinkedIn company scanner — discovers employee profiles and infers email formats."""

import re
from typing import Any
from urllib.parse import quote_plus

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20

# Matches LinkedIn profile URLs in search result bodies
_LINKEDIN_PROFILE_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/([\w\-]+)",
    re.IGNORECASE,
)
# Pull a display name from the DDG snippet, e.g. "Jane Doe - Software Engineer at Acme"
_PROFILE_TITLE_RE = re.compile(r"^(.+?)\s+[-–]\s+(.+)$")

_COMMON_EMAIL_FORMATS = [
    "{first}.{last}@{domain}",
    "{first}@{domain}",
    "{f}{last}@{domain}",
    "{first}{last}@{domain}",
    "{last}@{domain}",
]


def _slug_from_domain(domain: str) -> str:
    """Convert a domain name to a likely LinkedIn company URL slug."""
    # Strip TLD suffixes and use the first label
    return domain.split(".")[0].lower()


def _infer_email_format(profiles: list[dict[str, str]], domain: str) -> str:
    """Return the most probable email format for a domain given sample profiles.

    Without confirmed data we default to the most common enterprise pattern.
    """
    if not profiles:
        return f"{{first}}.{{last}}@{domain}"

    # Heuristic: use the most common format template
    return f"{{first}}.{{last}}@{domain}"


class LinkedInCompanyScanner(BaseOsintScanner):
    """Searches DuckDuckGo for LinkedIn profiles associated with a company domain
    and infers the organisation's email naming convention."""

    scanner_name = "linkedin_company"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.USERNAME})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if input_type == ScanInputType.DOMAIN:
            company_name = _slug_from_domain(input_value)
            domain = input_value
        else:
            # USERNAME treated as company name / slug
            company_name = input_value
            domain = ""

        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; OSINT-Scanner/1.0; "
                    "+https://github.com/osint-platform)"
                )
            },
        ) as client:
            ddg_profiles, ddg_urls = await self._ddg_search(client, company_name, domain)
            linkedin_company_url = await self._check_company_page(client, company_name)

        email_format = _infer_email_format(ddg_profiles, domain) if domain else ""

        identifiers: list[str] = (
            [f"url:{url}" for url in ddg_urls]
            + [f"person:{p['name']}" for p in ddg_profiles if p.get("name")]
        )
        if linkedin_company_url:
            identifiers.insert(0, f"url:{linkedin_company_url}")

        return {
            "company_name": company_name,
            "domain": domain,
            "linkedin_url": linkedin_company_url,
            "employee_count_estimate": len(ddg_profiles),
            "sample_profiles": ddg_profiles,
            "inferred_email_format": email_format,
            "found": bool(ddg_profiles or linkedin_company_url),
            "extracted_identifiers": identifiers,
        }

    async def _ddg_search(
        self,
        client: httpx.AsyncClient,
        company_name: str,
        domain: str,
    ) -> tuple[list[dict[str, str]], list[str]]:
        """Query DuckDuckGo Instant Answer API for LinkedIn profiles."""
        query = f'site:linkedin.com/in/ "{company_name}"'
        if domain:
            query += f' "{domain}"'

        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
        }

        try:
            resp = await client.get(url, params=params)

            if resp.status_code == 429:
                raise RateLimitError("DuckDuckGo API rate limited")
            if resp.status_code != 200:
                log.warning("DDG API unexpected response", status=resp.status_code, query=query)
                return [], []

            data = resp.json()
            profiles: list[dict[str, str]] = []
            all_urls: list[str] = []

            # Process RelatedTopics
            for topic in data.get("RelatedTopics", []):
                first_url: str = topic.get("FirstURL", "") or ""
                text: str = topic.get("Text", "") or ""

                profile_match = _LINKEDIN_PROFILE_RE.search(first_url)
                if not profile_match:
                    # Sometimes the URL is nested under a Topics sub-list
                    for sub in topic.get("Topics", []):
                        sub_url = sub.get("FirstURL", "") or ""
                        sub_text = sub.get("Text", "") or ""
                        sub_match = _LINKEDIN_PROFILE_RE.search(sub_url)
                        if sub_match:
                            profile = self._parse_profile(sub_url, sub_text)
                            if profile:
                                profiles.append(profile)
                                all_urls.append(sub_url)
                    continue

                profile = self._parse_profile(first_url, text)
                if profile:
                    profiles.append(profile)
                    all_urls.append(first_url)

            log.info(
                "DDG LinkedIn search completed",
                company=company_name,
                profiles_found=len(profiles),
            )
            return profiles, all_urls

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("DDG LinkedIn search failed", company=company_name, error=str(exc))
            return [], []

    @staticmethod
    def _parse_profile(linkedin_url: str, text: str) -> dict[str, str] | None:
        """Extract a structured profile dict from a DDG result entry."""
        slug_match = _LINKEDIN_PROFILE_RE.search(linkedin_url)
        if not slug_match:
            return None

        slug = slug_match.group(1)
        # Convert slug like "jane-doe-123abc" to a human name
        parts = slug.split("-")
        # Drop trailing numeric IDs
        name_parts = [p for p in parts if not p.isdigit()]
        display_name = " ".join(p.capitalize() for p in name_parts)

        title = ""
        title_match = _PROFILE_TITLE_RE.match(text)
        if title_match:
            display_name = title_match.group(1).strip()
            title = title_match.group(2).strip()

        return {
            "name": display_name,
            "title": title,
            "linkedin_url": linkedin_url,
            "slug": slug,
        }

    async def _check_company_page(
        self,
        client: httpx.AsyncClient,
        company_slug: str,
    ) -> str | None:
        """Probe the canonical LinkedIn company page URL."""
        url = f"https://www.linkedin.com/company/{company_slug}/"
        try:
            resp = await client.head(url)

            if resp.status_code == 429:
                raise RateLimitError("LinkedIn rate limited")

            if resp.status_code in {200, 301, 302}:
                log.debug("LinkedIn company page found", slug=company_slug)
                return url

            return None

        except RateLimitError:
            raise
        except Exception as exc:
            log.debug("LinkedIn company page check failed", slug=company_slug, error=str(exc))
            return None
