"""Cloud storage exposure scanner.

Queries GrayhatWarfare.com API for publicly exposed S3/Azure/GCP buckets
associated with a target domain or org name.
Requires GRAYHATWARFARE_API_KEY environment variable (free tier available).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


_SENSITIVE_EXTENSIONS = frozenset(
    {".env", ".pem", ".key", ".sql", ".bak", ".cfg", ".config", ".json", ".xml",
     ".yaml", ".yml", ".csv", ".db", ".sqlite", ".tar", ".gz", ".zip", ".credentials"}
)

_SENSITIVE_FILENAMES = frozenset(
    {"credentials", "secret", "password", "passwd", "private", "id_rsa", "id_dsa",
     ".env", "config", "backup", "dump"}
)


@dataclass
class BucketResult:
    name: str
    provider: str
    url: str
    is_public: bool = True
    file_count: int = 0
    sample_files: list[str] = field(default_factory=list)
    has_sensitive_files: bool = False
    sensitive_file_count: int = 0


@dataclass
class CloudExposureScanResult:
    target: str
    total_buckets: int = 0
    public_buckets: int = 0
    sensitive_findings: int = 0
    buckets: list[dict[str, Any]] = field(default_factory=list)


def _is_sensitive(filename: str) -> bool:
    lower = filename.lower()
    if any(lower.endswith(ext) for ext in _SENSITIVE_EXTENSIONS):
        return True
    return any(name in lower for name in _SENSITIVE_FILENAMES)


class CloudExposureScanner:
    """Scan for exposed cloud storage buckets via GrayhatWarfare API."""

    _BASE_URL = "https://buckets.grayhatwarfare.com/api/v1"
    _TIMEOUT = 30.0

    def __init__(self) -> None:
        self._api_key = os.getenv("GRAYHATWARFARE_API_KEY", "")

    async def scan(self, target: str) -> CloudExposureScanResult:
        """Scan for exposed buckets matching the target domain/org."""
        result = CloudExposureScanResult(target=target)

        if not self._api_key:
            # No API key — return mock structure indicating config needed
            result.buckets = [
                {
                    "name": "GRAYHATWARFARE_API_KEY not configured",
                    "provider": "N/A",
                    "url": "",
                    "is_public": False,
                    "file_count": 0,
                    "sample_files": [],
                    "has_sensitive_files": False,
                    "sensitive_file_count": 0,
                }
            ]
            return result

        try:
            buckets = await self._query_grayhatwarfare(target)
            result.total_buckets = len(buckets)
            result.public_buckets = sum(1 for b in buckets if b.is_public)
            result.sensitive_findings = sum(1 for b in buckets if b.has_sensitive_files)
            result.buckets = [
                {
                    "name": b.name,
                    "provider": b.provider,
                    "url": b.url,
                    "is_public": b.is_public,
                    "file_count": b.file_count,
                    "sample_files": b.sample_files,
                    "has_sensitive_files": b.has_sensitive_files,
                    "sensitive_file_count": b.sensitive_file_count,
                }
                for b in buckets
            ]
        except Exception as exc:
            result.buckets = [{"error": str(exc), "provider": "N/A", "name": "API Error", "url": "", "is_public": False, "file_count": 0, "sample_files": [], "has_sensitive_files": False, "sensitive_file_count": 0}]

        return result

    async def _query_grayhatwarfare(self, target: str) -> list[BucketResult]:
        """Query GrayhatWarfare API for buckets matching the target."""
        async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
            resp = await client.get(
                f"{self._BASE_URL}/buckets",
                params={"keywords": target, "access_token": self._api_key, "limit": 100},
                headers={"User-Agent": "OSINT-Platform/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()

        buckets: list[BucketResult] = []
        for item in data.get("buckets", []):
            name = item.get("bucket", "")
            provider = self._infer_provider(name, item.get("url", ""))
            sample_files = [f.get("filename", "") for f in item.get("files", [])[:10]]
            sensitive_files = [f for f in sample_files if _is_sensitive(f)]

            buckets.append(
                BucketResult(
                    name=name,
                    provider=provider,
                    url=item.get("url", f"https://{name}.s3.amazonaws.com"),
                    is_public=True,
                    file_count=item.get("fileCount", 0),
                    sample_files=sample_files,
                    has_sensitive_files=len(sensitive_files) > 0,
                    sensitive_file_count=len(sensitive_files),
                )
            )

        return buckets

    @staticmethod
    def _infer_provider(name: str, url: str) -> str:
        combined = (name + url).lower()
        if "amazonaws.com" in combined or "s3." in combined:
            return "AWS S3"
        if "blob.core.windows.net" in combined or "azure" in combined:
            return "Azure Blob"
        if "storage.googleapis.com" in combined or "gcs" in combined:
            return "GCP Storage"
        return "Unknown"
