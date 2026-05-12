"""Cloud Storage Hunter — discovers exposed S3, Azure Blob, and GCP Storage buckets.

Module 103 in the Infrastructure & Exploitation domain. Generates common bucket/container
name variations derived from the target domain and probes AWS S3, Azure Blob Storage,
and Google Cloud Storage endpoints to identify publicly accessible or listing-enabled
storage buckets. Distinct from the existing cloud_asset_scanner which focuses on
DNS-based cloud enumeration.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


def _extract_domain_base(domain: str) -> str:
    """Extract the meaningful part of a domain for bucket name generation."""
    domain = domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    parts = domain.split(".")
    # Use second-level domain (e.g., 'example' from 'example.com')
    if len(parts) >= 2:
        return parts[-2]
    return parts[0]


def _generate_bucket_names(base: str) -> list[str]:
    """Generate common bucket name variations from a domain base word."""
    variations = [
        base,
        f"{base}-backup",
        f"{base}-backups",
        f"{base}-data",
        f"{base}-assets",
        f"{base}-static",
        f"{base}-media",
        f"{base}-uploads",
        f"{base}-files",
        f"{base}-dev",
        f"{base}-staging",
        f"{base}-prod",
        f"{base}-production",
        f"{base}-private",
        f"{base}-public",
        f"{base}-logs",
        f"{base}-archive",
        f"{base}-images",
        f"{base}-docs",
        f"{base}-storage",
        f"backup-{base}",
        f"data-{base}",
        f"assets-{base}",
    ]
    return list(dict.fromkeys(variations))  # Deduplicate while preserving order


def _build_probe_urls(bucket: str) -> list[dict[str, str]]:
    """Build probe URLs for S3, Azure Blob, and GCP Storage."""
    return [
        {
            "provider": "AWS S3",
            "url": f"https://{bucket}.s3.amazonaws.com/",
        },
        {
            "provider": "AWS S3 (path-style)",
            "url": f"https://s3.amazonaws.com/{bucket}/",
        },
        {
            "provider": "Azure Blob",
            "url": f"https://{bucket}.blob.core.windows.net/",
        },
        {
            "provider": "GCP Storage",
            "url": f"https://storage.googleapis.com/{bucket}/",
        },
    ]


async def _probe_bucket(client: httpx.AsyncClient, provider: str, url: str, bucket: str) -> dict[str, Any] | None:
    """Probe a single cloud storage URL and classify the response."""
    try:
        resp = await client.get(url, follow_redirects=False)
        status = resp.status_code

        # 200 = public listing enabled; 403 = exists but private; 404 = does not exist
        if status in (200, 403):
            is_public = status == 200
            has_listing = is_public and ("ListBucketResult" in resp.text or "<Contents>" in resp.text or "<?xml" in resp.text)
            return {
                "bucket": bucket,
                "provider": provider,
                "url": url,
                "status_code": status,
                "exists": True,
                "public": is_public,
                "listing_enabled": has_listing,
                "risk": "Critical" if has_listing else ("High" if is_public else "Medium"),
            }
    except (httpx.RequestError, httpx.TimeoutException):
        pass
    return None


class CloudStorageHunterScanner(BaseOsintScanner):
    """Discovers exposed cloud storage buckets derived from the target domain.

    Generates bucket name variations and probes AWS S3, Azure Blob, and GCP
    Storage endpoints. Reports buckets that exist and their access permissions.
    Only uses the user-supplied domain to generate names (Module 103).
    """

    scanner_name = "cloud_storage_hunter"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base = _extract_domain_base(input_value)
        buckets = _generate_bucket_names(base)

        found_buckets: list[dict[str, Any]] = []
        public_buckets: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            for bucket in buckets:
                probe_targets = _build_probe_urls(bucket)
                tasks = [_probe_bucket(client, p["provider"], p["url"], bucket) for p in probe_targets]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, dict):
                        found_buckets.append(result)
                        if result.get("public"):
                            public_buckets.append(result)

        return {
            "target_domain": input_value,
            "domain_base": base,
            "bucket_names_tested": buckets,
            "found": len(found_buckets) > 0,
            "existing_buckets": found_buckets,
            "public_buckets": public_buckets,
            "public_count": len(public_buckets),
            "severity": "Critical" if any(b.get("listing_enabled") for b in found_buckets)
                        else ("High" if public_buckets else "None"),
            "educational_note": (
                "Exposed cloud storage buckets are a leading cause of data breaches. "
                "Attackers enumerate predictable bucket names derived from company names. "
                "Enable bucket ACLs, disable public access, and audit bucket policies regularly."
            ),
        }
