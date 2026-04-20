"""Cloud metadata scanner — lists contents of public cloud storage buckets and
flags sensitive files."""

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20

# S3 XML namespace
_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

# Patterns that suggest a file may contain secrets or sensitive data
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.env$", re.IGNORECASE),
    re.compile(r"\.sql(\.gz|\.bz2|\.zip)?$", re.IGNORECASE),
    re.compile(r"\.bak$", re.IGNORECASE),
    re.compile(r"\.config$", re.IGNORECASE),
    re.compile(r"\.conf$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"(^|/)backup", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"credentials", re.IGNORECASE),
    re.compile(r"secrets?\.ya?ml$", re.IGNORECASE),
    re.compile(r"\.tfstate$", re.IGNORECASE),
    re.compile(r"dump\.(sql|tar|gz)$", re.IGNORECASE),
]


def _is_sensitive(key: str) -> bool:
    return any(pattern.search(key) for pattern in _SENSITIVE_PATTERNS)


def _detect_provider(url: str) -> str | None:
    """Identify the cloud provider from a public bucket URL."""
    if "s3.amazonaws.com" in url or "amazonaws.com" in url:
        return "s3"
    if "blob.core.windows.net" in url:
        return "azure"
    if "storage.googleapis.com" in url:
        return "gcp"
    return None


def _extract_bucket_from_url(url: str, provider: str) -> str:
    """Parse the bucket name from a public cloud storage URL."""
    parsed = urlparse(url)

    if provider == "s3":
        # https://{bucket}.s3.amazonaws.com/...
        host = parsed.netloc
        return host.split(".")[0]

    if provider == "azure":
        # https://{account}.blob.core.windows.net/{container}/...
        host = parsed.netloc
        account = host.split(".")[0]
        path_parts = parsed.path.strip("/").split("/")
        container = path_parts[0] if path_parts else ""
        return f"{account}/{container}" if container else account

    if provider == "gcp":
        # https://storage.googleapis.com/{bucket}/...
        path_parts = parsed.path.strip("/").split("/")
        return path_parts[0] if path_parts else parsed.path

    return parsed.netloc


class CloudMetadataScanner(BaseOsintScanner):
    """Given a public cloud storage URL, lists the bucket contents using the
    provider's listing API and identifies potentially sensitive files."""

    scanner_name = "cloud_metadata"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 21600  # 6 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        provider = _detect_provider(input_value)
        if provider is None:
            return {
                "input_url": input_value,
                "found": False,
                "error": (
                    "URL does not appear to be an S3, Azure Blob, or GCP storage URL. "
                    "Expected hostnames containing s3.amazonaws.com, "
                    "blob.core.windows.net, or storage.googleapis.com."
                ),
                "extracted_identifiers": [],
            }

        bucket_name = _extract_bucket_from_url(input_value, provider)
        log.info("Cloud metadata scan", provider=provider, bucket=bucket_name, url=input_value)

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            if provider == "s3":
                file_listing, base_url = await self._list_s3(client, bucket_name, input_value)
            elif provider == "gcp":
                file_listing, base_url = await self._list_gcp(client, bucket_name, input_value)
            else:
                # Azure listing requires additional auth context; return metadata only
                log.info("Azure bucket listing not supported without credentials", bucket=bucket_name)
                return {
                    "input_url": input_value,
                    "provider": "azure",
                    "bucket_name": bucket_name,
                    "found": True,
                    "total_objects": 0,
                    "note": "Azure Blob storage listing requires account credentials.",
                    "sensitive_files": [],
                    "file_listing": [],
                    "extracted_identifiers": [],
                }

        if file_listing is None:
            return {
                "input_url": input_value,
                "provider": provider,
                "bucket_name": bucket_name,
                "found": False,
                "error": "Bucket listing returned no data (may be private or non-existent)",
                "extracted_identifiers": [],
            }

        sensitive: list[dict[str, Any]] = [
            f for f in file_listing if _is_sensitive(f.get("key", ""))
        ]

        sensitive_urls = [f"{base_url.rstrip('/')}/{f['key']}" for f in sensitive]
        identifiers = [f"url:{u}" for u in sensitive_urls]

        return {
            "input_url": input_value,
            "provider": provider,
            "bucket_name": bucket_name,
            "found": True,
            "total_objects": len(file_listing),
            "sensitive_files": sensitive,
            "sensitive_file_urls": sensitive_urls,
            "file_listing": file_listing,
            "extracted_identifiers": identifiers,
        }

    # ------------------------------------------------------------------ S3
    async def _list_s3(
        self,
        client: httpx.AsyncClient,
        bucket_name: str,
        original_url: str,
    ) -> tuple[list[dict[str, Any]] | None, str]:
        """List S3 bucket contents using the ListObjectsV2 API."""
        # Normalise to virtual-hosted style base URL
        parsed = urlparse(original_url)
        if "s3.amazonaws.com" in parsed.netloc:
            base_url = f"https://{parsed.netloc}"
        else:
            base_url = f"https://{bucket_name}.s3.amazonaws.com"

        list_url = f"{base_url}/"
        params = {"list-type": "2", "max-keys": "100"}

        try:
            resp = await client.get(list_url, params=params)

            if resp.status_code == 429:
                raise RateLimitError("S3 rate limited")
            if resp.status_code == 403:
                log.info("S3 bucket is private (403)", bucket=bucket_name)
                return None, base_url
            if resp.status_code != 200:
                log.warning("S3 list unexpected status", status=resp.status_code, bucket=bucket_name)
                return None, base_url

            return self._parse_s3_xml(resp.text), base_url

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("S3 list failed", bucket=bucket_name, error=str(exc))
            return None, base_url

    @staticmethod
    def _parse_s3_xml(xml_text: str) -> list[dict[str, Any]]:
        """Parse the S3 ListObjectsV2 XML response into a list of file records."""
        try:
            root = ET.fromstring(xml_text)
            ns = _S3_NS if root.tag.startswith("{http://s3.amazonaws.com") else {}
            prefix = "s3:" if ns else ""

            files: list[dict[str, Any]] = []
            for content in root.iter(f"{'{' + _S3_NS['s3'] + '}' if ns else ''}Contents"):
                key_el = content.find(f"{prefix}Key", ns) if ns else content.find("Key")
                size_el = content.find(f"{prefix}Size", ns) if ns else content.find("Size")
                modified_el = content.find(f"{prefix}LastModified", ns) if ns else content.find("LastModified")

                files.append(
                    {
                        "key": key_el.text if key_el is not None else "",
                        "size_bytes": int(size_el.text) if size_el is not None and size_el.text else 0,
                        "last_modified": modified_el.text if modified_el is not None else "",
                    }
                )
            return files
        except ET.ParseError as exc:
            log.warning("S3 XML parse error", error=str(exc))
            return []

    # ------------------------------------------------------------------ GCP
    async def _list_gcp(
        self,
        client: httpx.AsyncClient,
        bucket_name: str,
        original_url: str,
    ) -> tuple[list[dict[str, Any]] | None, str]:
        """List GCP Storage bucket contents using the JSON API."""
        base_url = f"https://storage.googleapis.com/{bucket_name}"
        json_api_url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o"
        params = {"maxResults": "100", "projection": "noAcl"}

        try:
            resp = await client.get(json_api_url, params=params)

            if resp.status_code == 429:
                raise RateLimitError("GCP Storage rate limited")
            if resp.status_code == 403:
                log.info("GCP bucket is private (403)", bucket=bucket_name)
                return None, base_url
            if resp.status_code != 200:
                log.warning("GCP list unexpected status", status=resp.status_code, bucket=bucket_name)
                return None, base_url

            data = resp.json()
            items: list[dict[str, Any]] = data.get("items", [])

            files = [
                {
                    "key": item.get("name", ""),
                    "size_bytes": int(item.get("size", 0)),
                    "last_modified": item.get("updated", ""),
                }
                for item in items
            ]
            return files, base_url

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("GCP list failed", bucket=bucket_name, error=str(exc))
            return None, base_url
