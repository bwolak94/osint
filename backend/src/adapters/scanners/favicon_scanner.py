"""Favicon hash scanner — identifies servers sharing the same favicon fingerprint."""

import base64
import hashlib
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20


def _compute_favicon_hash(content: bytes) -> tuple[str, str]:
    """Compute mmh3 hash (Shodan-style) with SHA-256 fallback.

    Returns a tuple of (hash_value, hash_algorithm).
    The mmh3 hash is computed over the base64-encoded content, matching Shodan's
    methodology: base64-encode the raw bytes, then mmh3-hash the encoded string.
    """
    try:
        import mmh3

        encoded = base64.encodebytes(content).decode("ascii")
        favicon_hash = str(mmh3.hash(encoded))
        return favicon_hash, "mmh3"
    except ImportError:
        log.warning("mmh3 not installed, falling back to SHA-256 for favicon hash")
        sha256 = hashlib.sha256(content).hexdigest()
        return sha256, "sha256"


def _extract_domain(input_value: str, input_type: ScanInputType) -> str:
    """Derive a bare hostname from either a DOMAIN or a URL input."""
    if input_type == ScanInputType.URL:
        parsed = urlparse(input_value)
        return parsed.netloc or input_value
    return input_value


class FaviconHashScanner(BaseOsintScanner):
    """Fetches a site's favicon, computes its hash, and queries Shodan InternetDB
    to find other hosts sharing the same fingerprint."""

    scanner_name = "favicon_hash"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = _extract_domain(input_value, input_type)

        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        ) as client:
            favicon_content = await self._fetch_favicon(client, domain)

            if favicon_content is None:
                return {
                    "domain": domain,
                    "found": False,
                    "error": "Favicon not found or unreachable",
                    "extracted_identifiers": [],
                }

            favicon_hash, hash_algorithm = _compute_favicon_hash(favicon_content)
            log.info(
                "Favicon hash computed",
                domain=domain,
                hash=favicon_hash,
                algorithm=hash_algorithm,
            )

            shodan_data = await self._query_shodan(client, favicon_hash, hash_algorithm)

            related_ips: list[str] = shodan_data.get("related_ips", [])
            related_domains: list[str] = shodan_data.get("related_domains", [])

            identifiers: list[str] = (
                [f"ip:{ip}" for ip in related_ips]
                + [f"domain:{d}" for d in related_domains]
            )

            return {
                "domain": domain,
                "found": True,
                "favicon_hash": favicon_hash,
                "hash_algorithm": hash_algorithm,
                "favicon_size_bytes": len(favicon_content),
                "related_ips": related_ips,
                "related_domains": related_domains,
                "shodan_queried": hash_algorithm == "mmh3",
                "extracted_identifiers": identifiers,
            }

    async def _fetch_favicon(self, client: httpx.AsyncClient, domain: str) -> bytes | None:
        """Attempt to fetch /favicon.ico from both HTTPS and HTTP."""
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}/favicon.ico"
            try:
                resp = await client.get(url)
                if resp.status_code == 429:
                    raise RateLimitError("Rate limited fetching favicon")
                if resp.status_code == 200 and resp.content:
                    log.debug("Favicon fetched", url=url, size=len(resp.content))
                    return resp.content
            except RateLimitError:
                raise
            except Exception as exc:
                log.debug("Favicon fetch attempt failed", url=url, error=str(exc))
        return None

    async def _query_shodan(
        self,
        client: httpx.AsyncClient,
        favicon_hash: str,
        hash_algorithm: str,
    ) -> dict[str, Any]:
        """Query Shodan InternetDB for hosts sharing the same favicon hash.

        Only possible when the mmh3 algorithm was used (Shodan-compatible hash).
        """
        if hash_algorithm != "mmh3":
            log.info("Skipping Shodan query — non-mmh3 hash, no API key required but hash incompatible")
            return {"related_ips": [], "related_domains": []}

        url = f"https://internetdb.shodan.io/favicon/{favicon_hash}"
        try:
            resp = await client.get(url)

            if resp.status_code == 429:
                raise RateLimitError("Shodan InternetDB rate limited")
            if resp.status_code == 404:
                log.info("No Shodan results for favicon hash", hash=favicon_hash)
                return {"related_ips": [], "related_domains": []}
            if resp.status_code != 200:
                log.warning("Unexpected Shodan response", status=resp.status_code, hash=favicon_hash)
                return {"related_ips": [], "related_domains": []}

            data = resp.json()
            ips: list[str] = data.get("ips", [])
            hostnames: list[str] = data.get("hostnames", [])
            return {"related_ips": ips, "related_domains": hostnames}

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("Shodan favicon query failed", hash=favicon_hash, error=str(exc))
            return {"related_ips": [], "related_domains": []}
