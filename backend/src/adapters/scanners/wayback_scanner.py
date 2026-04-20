"""Wayback Machine scanner — discovers historical snapshots via the CDX API."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 30
_CDX_API_URL = "https://web.archive.org/cdx/search/cdx"


class WaybackScanner(BaseOsintScanner):
    """Queries the Wayback Machine CDX API for archived snapshots of a URL or domain."""

    scanner_name = "wayback"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(
                _CDX_API_URL,
                params={
                    "url": input_value,
                    "output": "json",
                    "fl": "timestamp,original,statuscode,mimetype",
                    "limit": "100",
                    "collapse": "urlkey",
                },
            )

            if resp.status_code == 404:
                return self._empty_result(input_value)

            resp.raise_for_status()
            data = resp.json()

        # CDX API returns a list of lists; the first row is the header
        if not data or len(data) <= 1:
            return self._empty_result(input_value)

        headers = data[0]
        rows = data[1:]

        snapshots: list[dict[str, str]] = []
        urls_seen: set[str] = set()

        for row in rows:
            entry = dict(zip(headers, row))
            snapshot = {
                "timestamp": entry.get("timestamp", ""),
                "url": entry.get("original", ""),
                "status": entry.get("statuscode", ""),
                "mimetype": entry.get("mimetype", ""),
            }
            snapshots.append(snapshot)
            url = entry.get("original", "")
            if url:
                urls_seen.add(url)

        timestamps = [s["timestamp"] for s in snapshots if s["timestamp"]]
        first_seen = min(timestamps) if timestamps else None
        last_seen = max(timestamps) if timestamps else None

        identifiers = [f"url:{url}" for url in sorted(urls_seen)]

        return {
            "input": input_value,
            "found": True,
            "snapshot_count": len(snapshots),
            "snapshots": snapshots,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "extracted_identifiers": identifiers,
        }

    @staticmethod
    def _empty_result(input_value: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "snapshot_count": 0,
            "snapshots": [],
            "first_seen": None,
            "last_seen": None,
            "extracted_identifiers": [],
        }
