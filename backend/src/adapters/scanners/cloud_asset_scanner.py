"""Cloud asset scanner — discovers exposed S3, Azure Blob, and GCP storage buckets."""

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 10
_MAX_CONCURRENT = 20


def _build_bucket_names(domain: str) -> list[str]:
    """Generate plausible bucket name candidates from a domain."""
    # Strip scheme if accidentally included
    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    host = parsed.netloc or domain
    # Remove port if present
    host = host.split(":")[0]

    # Short name = everything before the first dot
    short_name = host.split(".")[0]

    base_variants = [
        host,
        short_name,
    ]
    suffixes = [
        "-backup",
        "-dev",
        "-staging",
        "-prod",
        "-data",
        "-assets",
        "-files",
        "-media",
        "-static",
        "-logs",
        "-archive",
        "-uploads",
        "-downloads",
        "-public",
    ]

    names: list[str] = list(base_variants)
    for base in base_variants:
        for suffix in suffixes:
            names.append(f"{base}{suffix}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


class CloudAssetScanner(BaseOsintScanner):
    """Enumerates likely cloud storage buckets (S3 / Azure Blob / GCP) for a domain
    by probing name permutations concurrently."""

    scanner_name = "cloud_assets"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        bucket_names = _build_bucket_names(input_value)
        log.info("Cloud asset scan starting", domain=input_value, candidates=len(bucket_names))

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        found_buckets: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=False,
        ) as client:
            tasks = [
                self._check_all_providers(client, semaphore, bucket)
                for bucket in bucket_names
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                found_buckets.extend(result)
            elif isinstance(result, Exception):
                log.debug("Bucket check raised exception", error=str(result))

        identifiers = [f"url:{b['url']}" for b in found_buckets]

        return {
            "domain": input_value,
            "found": bool(found_buckets),
            "buckets_checked": len(bucket_names),
            "found_buckets": found_buckets,
            "found_count": len(found_buckets),
            "extracted_identifiers": identifiers,
        }

    async def _check_all_providers(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        bucket: str,
    ) -> list[dict[str, Any]]:
        """Check a single bucket name across all three cloud providers."""
        async with semaphore:
            tasks = [
                self._check_s3(client, bucket),
                self._check_azure(client, bucket),
                self._check_gcp(client, bucket),
            ]
            provider_results = await asyncio.gather(*tasks, return_exceptions=True)

        found: list[dict[str, Any]] = []
        for r in provider_results:
            if isinstance(r, dict):
                found.append(r)
        return found

    async def _check_s3(self, client: httpx.AsyncClient, bucket: str) -> dict[str, Any] | None:
        url = f"https://{bucket}.s3.amazonaws.com/"
        return await self._probe(client, bucket, "s3", url)

    async def _check_azure(self, client: httpx.AsyncClient, bucket: str) -> dict[str, Any] | None:
        url = f"https://{bucket}.blob.core.windows.net/"
        return await self._probe(client, bucket, "azure", url)

    async def _check_gcp(self, client: httpx.AsyncClient, bucket: str) -> dict[str, Any] | None:
        url = f"https://storage.googleapis.com/{bucket}"
        return await self._probe(client, bucket, "gcp", url)

    async def _probe(
        self,
        client: httpx.AsyncClient,
        bucket: str,
        provider: str,
        url: str,
    ) -> dict[str, Any] | None:
        """Send a HEAD request; interpret 200/403 as 'bucket exists'."""
        try:
            resp = await client.head(url)

            if resp.status_code == 429:
                raise RateLimitError(f"Rate limited probing {provider}")

            if resp.status_code in {200, 403}:
                public_readable = resp.status_code == 200
                log.info(
                    "Cloud bucket found",
                    provider=provider,
                    bucket=bucket,
                    public=public_readable,
                )
                return {
                    "provider": provider,
                    "bucket_name": bucket,
                    "public_readable": public_readable,
                    "url": url,
                    "http_status": resp.status_code,
                }

            return None

        except RateLimitError:
            raise
        except Exception as exc:
            log.debug("Bucket probe failed", provider=provider, bucket=bucket, error=str(exc))
            return None
