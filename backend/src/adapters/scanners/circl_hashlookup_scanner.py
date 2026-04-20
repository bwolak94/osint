"""CIRCL hash-lookup scanner — checks file hashes against the CIRCL known-good database."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_HASHLOOKUP_BASE = "https://hashlookup.circl.lu"

# Regex patterns keyed by (hash_type, expected_hex_length)
_HASH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("md5", re.compile(r"^[0-9a-fA-F]{32}$")),
    ("sha1", re.compile(r"^[0-9a-fA-F]{40}$")),
    ("sha256", re.compile(r"^[0-9a-fA-F]{64}$")),
]


def _detect_hash_type(value: str) -> str | None:
    """Return 'md5', 'sha1', 'sha256', or None if the value is not a hash."""
    for hash_type, pattern in _HASH_PATTERNS:
        if pattern.match(value):
            return hash_type
    return None


class CIRLHashlookupScanner(BaseOsintScanner):
    """Queries the CIRCL hashlookup service to determine if a file hash is known-good.

    No API key required — the service is completely free.

    Input type is URL (as a proxy for "hash value" in the scanner's type system).
    The scanner auto-detects whether the supplied value is an MD5 (32 hex chars),
    SHA-1 (40 hex chars), or SHA-256 (64 hex chars) hash and queries the
    appropriate CIRCL endpoint.

    If the value is not a recognised hash pattern the scanner returns
    ``found=False`` without making a network request.

    Returns:
    - ``is_known``: whether the hash appears in the CIRCL database (NSRL / software catalogs).
    - ``is_malicious``: logical inverse of ``is_known`` (unknown files may be malicious).
    - ``file_info``: full file metadata returned by CIRCL (FileName, FileSize, etc.).
    - ``source``: source database name (e.g. "NSRL").
    """

    scanner_name = "circl_hashlookup"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400  # 24 hours — hash lookups are stable

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        hash_type = _detect_hash_type(input_value)
        if hash_type is None:
            return {
                "input": input_value,
                "found": False,
                "is_known": False,
                "is_malicious": None,
                "error": "Input does not look like an MD5, SHA-1, or SHA-256 hash",
                "extracted_identifiers": [],
            }

        return await self._lookup(input_value, hash_type)

    async def _lookup(self, hash_value: str, hash_type: str) -> dict[str, Any]:
        url = f"{_HASHLOOKUP_BASE}/lookup/{hash_type}/{hash_value}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})

        if resp.status_code == 404:
            return {
                "input": hash_value,
                "hash_type": hash_type,
                "found": False,
                "is_known": False,
                "is_malicious": True,  # Not in known-good DB — treat as potentially malicious
                "file_info": {},
                "source": None,
                "extracted_identifiers": [],
            }

        if resp.status_code != 200:
            log.warning("CIRCL hashlookup unexpected status", status=resp.status_code, hash=hash_value)
            return {
                "input": hash_value,
                "hash_type": hash_type,
                "found": False,
                "is_known": False,
                "is_malicious": None,
                "extracted_identifiers": [],
            }

        data = resp.json()

        # The API returns the file record directly or an error key
        if "message" in data and "NotFound" in str(data.get("message", "")):
            return {
                "input": hash_value,
                "hash_type": hash_type,
                "found": False,
                "is_known": False,
                "is_malicious": True,
                "file_info": {},
                "source": None,
                "extracted_identifiers": [],
            }

        source = data.get("KnownMalicious", None)
        is_known_good = True  # Present in CIRCL DB means it is a known-good file
        is_malicious = bool(source)  # KnownMalicious flag takes priority when present

        return {
            "input": hash_value,
            "hash_type": hash_type,
            "found": True,
            "is_known": is_known_good,
            "is_malicious": is_malicious,
            "file_info": {
                "file_name": data.get("FileName"),
                "file_size": data.get("FileSize"),
                "crc32": data.get("CRC32"),
                "md5": data.get("MD5"),
                "sha1": data.get("SHA-1"),
                "sha256": data.get("SHA-256"),
                "sha512": data.get("SHA-512"),
                "ssdeep": data.get("SSDEEP"),
                "tlsh": data.get("TLSH"),
            },
            "source": data.get("source", "NSRL"),
            "product_name": data.get("ProductName"),
            "publisher": data.get("OpSystemCode") or data.get("SpecialCode"),
            "extracted_identifiers": [],  # Hash lookups — no pivot identifiers needed
        }
