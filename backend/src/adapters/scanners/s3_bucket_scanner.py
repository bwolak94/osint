"""S3 Bucket & Cloud Storage Exposure Scanner.

Discovers publicly accessible AWS S3 buckets, GCP Cloud Storage buckets,
and Azure Blob Storage containers associated with a target domain.
Exposed cloud storage is one of the most common causes of data breaches.

Manual-only scanner — probes predictable bucket name patterns.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# S3 bucket name patterns derived from domain/org name
def _generate_bucket_names(domain: str) -> list[str]:
    """Generate likely bucket names from domain."""
    # Extract org name from domain
    parts = domain.replace("www.", "").split(".")
    org = parts[0] if parts else domain

    candidates = [
        # Direct name variations
        org, f"{org}-assets", f"{org}-static", f"{org}-media",
        f"{org}-uploads", f"{org}-files", f"{org}-images",
        f"{org}-backup", f"{org}-backups", f"{org}-data",
        f"{org}-dev", f"{org}-staging", f"{org}-prod", f"{org}-production",
        f"{org}-test", f"{org}-demo", f"{org}-public", f"{org}-private",
        # Logs and exports
        f"{org}-logs", f"{org}-log", f"{org}-exports", f"{org}-reports",
        # Config and secrets
        f"{org}-config", f"{org}-configs", f"{org}-secrets", f"{org}-keys",
        # CDN / frontend
        f"{org}-cdn", f"{org}-web", f"{org}-www", f"{org}-frontend",
        # Infrastructure
        f"{org}-infra", f"{org}-terraform", f"{org}-ansible",
        # Common patterns
        f"assets.{domain}", f"static.{domain}", f"media.{domain}",
        # Full domain as bucket name
        domain.replace(".", "-"), domain,
    ]
    return list(dict.fromkeys(c.lower() for c in candidates if c))


# AWS S3 bucket URL patterns
def _s3_urls(bucket: str) -> list[tuple[str, str]]:
    return [
        (f"https://{bucket}.s3.amazonaws.com/", "s3_virtual_hosted"),
        (f"https://s3.amazonaws.com/{bucket}/", "s3_path_style"),
        (f"https://{bucket}.s3.us-east-1.amazonaws.com/", "s3_us_east_1"),
        (f"https://{bucket}.s3.eu-west-1.amazonaws.com/", "s3_eu_west_1"),
        (f"https://{bucket}.s3.ap-southeast-1.amazonaws.com/", "s3_ap_southeast_1"),
    ]

# GCP Cloud Storage
def _gcs_urls(bucket: str) -> list[tuple[str, str]]:
    return [
        (f"https://storage.googleapis.com/{bucket}/", "gcs"),
        (f"https://{bucket}.storage.googleapis.com/", "gcs_subdomain"),
    ]

# Azure Blob Storage
def _azure_urls(bucket: str) -> list[tuple[str, str]]:
    return [
        (f"https://{bucket}.blob.core.windows.net/", "azure_blob"),
        (f"https://{bucket}.blob.core.windows.net/public/", "azure_blob_public"),
    ]

# Status codes indicating public access
_PUBLIC_STATUS = {200, 206}
_EXISTS_STATUS = {200, 206, 403, 301, 302}  # 403 = exists but denied (still a finding)

# S3 XML response patterns
_S3_INDICATORS = re.compile(r"(?i)ListBucketResult|xmlns.*s3\.amazonaws\.com|<Key>|<Contents>|NoSuchBucket|AllAccessDisabled")
_GCS_INDICATORS = re.compile(r"(?i)storage\.googleapis\.com|<Key>|<ListBucketResult|AccessDenied")
_AZURE_INDICATORS = re.compile(r"(?i)BlobServiceProperties|<EnumerationResults|BlobPrefix|ResourceNotFound")


class S3BucketScanner(BaseOsintScanner):
    """Cloud storage exposure scanner (AWS S3, GCP, Azure Blob).

    Probes predictable bucket name patterns derived from the target domain
    across multiple cloud providers. Identifies:
    - Publicly listable buckets (critical — data exposure)
    - Existing but access-denied buckets (medium — confirms bucket exists)
    - File/object count when listing is allowed
    - Presence of sensitive file patterns in listed contents
    """

    scanner_name = "s3_bucket"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = _extract_domain(input_value, input_type)
        if not domain:
            return {"input": input_value, "error": "Could not extract domain", "extracted_identifiers": []}

        return await self._manual_scan(domain, input_value)

    async def _manual_scan(self, domain: str, input_value: str) -> dict[str, Any]:
        public_buckets: list[dict[str, Any]] = []
        restricted_buckets: list[dict[str, Any]] = []
        identifiers: list[str] = []

        bucket_names = _generate_bucket_names(domain)
        semaphore = asyncio.Semaphore(20)

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=False,
            verify=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BucketScanner/1.0)"},
        ) as client:

            async def check_bucket_url(bucket: str, url: str, provider: str, url_style: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.get(url)
                        body = resp.text[:4000]

                        if resp.status_code == 404 or "NoSuchBucket" in body:
                            return  # Doesn't exist

                        if resp.status_code in _PUBLIC_STATUS:
                            # Parse file listing
                            files: list[str] = []
                            if provider == "s3":
                                files = re.findall(r"<Key>([^<]+)</Key>", body)
                            elif provider == "gcs":
                                files = re.findall(r"<Key>([^<]+)</Key>", body)
                            elif provider == "azure":
                                files = re.findall(r"<Name>([^<]+)</Name>", body)

                            # Detect sensitive files
                            sensitive = [
                                f for f in files
                                if re.search(
                                    r"(?i)\.(sql|db|env|bak|backup|key|pem|p12|pfx|json|yaml|yml|csv|log)$|"
                                    r"(?i)(password|secret|credential|config|private|key|token)",
                                    f,
                                )
                            ]

                            public_buckets.append({
                                "bucket": bucket,
                                "url": url,
                                "provider": provider,
                                "style": url_style,
                                "status_code": resp.status_code,
                                "publicly_listable": True,
                                "file_count": len(files),
                                "sample_files": files[:10],
                                "sensitive_files": sensitive[:10],
                                "severity": "critical",
                            })
                            identifiers.append(f"vuln:cloud_storage:{provider}:{bucket}")

                        elif resp.status_code == 403:
                            # Bucket exists but access denied — still interesting
                            if _S3_INDICATORS.search(body) or _GCS_INDICATORS.search(body) or _AZURE_INDICATORS.search(body):
                                restricted_buckets.append({
                                    "bucket": bucket,
                                    "url": url,
                                    "provider": provider,
                                    "status_code": 403,
                                    "publicly_listable": False,
                                    "severity": "medium",
                                    "note": "Bucket exists but access denied",
                                })
                                identifiers.append(f"info:cloud_storage:{provider}:{bucket}")

                    except Exception:
                        pass

            # Build all tasks
            tasks = []
            for bucket in bucket_names:
                for url, style in _s3_urls(bucket):
                    tasks.append(check_bucket_url(bucket, url, "s3", style))
                for url, style in _gcs_urls(bucket):
                    tasks.append(check_bucket_url(bucket, url, "gcs", style))
                for url, style in _azure_urls(bucket):
                    tasks.append(check_bucket_url(bucket, url, "azure", style))

            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "domain": domain,
            "bucket_names_tested": len(bucket_names),
            "public_buckets": public_buckets,
            "restricted_buckets": restricted_buckets[:20],
            "total_public": len(public_buckets),
            "total_restricted": len(restricted_buckets),
            "is_critical": len(public_buckets) > 0,
            "providers_checked": ["s3", "gcs", "azure"],
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_domain(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return value.lstrip("*.").split(":")[0]
    try:
        return urlparse(value).hostname or ""
    except Exception:
        return ""
