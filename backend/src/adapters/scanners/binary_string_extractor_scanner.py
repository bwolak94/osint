"""Binary String Extractor — downloads a file and extracts printable strings.

Module 95 in the Infrastructure & Exploitation domain. Fetches the content at
the user-supplied URL (expected to be a binary or mixed file) and extracts
printable ASCII strings of length >= 6 characters — analogous to the UNIX
`strings` utility. Groups findings by category: URLs, IP addresses, email
addresses, and suspicious security keywords.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MIN_STRING_LEN = 6
_MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB cap

_RE_URL = re.compile(r"https?://[^\s\"'<>]{4,200}", re.IGNORECASE)
_RE_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_RE_PRINTABLE = re.compile(r"[ -~]{6,}")

_SUSPICIOUS_KEYWORDS = [
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "private key", "BEGIN RSA", "BEGIN EC", "BEGIN PRIVATE",
    "Authorization", "Bearer ", "AWS_ACCESS", "aws_secret", "AKIA",
    "connection string", "connectionstring", "jdbc:", "mongodb://",
    "redis://", "ftp://", "admin", "root", "credentials",
]


def _extract_strings(data: bytes) -> list[str]:
    """Extract printable ASCII strings from binary data."""
    text = data.decode("latin-1", errors="replace")
    return _RE_PRINTABLE.findall(text)


def _categorise_strings(strings: list[str]) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "urls": [],
        "ip_addresses": [],
        "emails": [],
        "suspicious_keywords": [],
        "all_strings": strings[:500],  # Cap raw list at 500 entries
    }

    seen_urls: set[str] = set()
    seen_ips: set[str] = set()
    seen_emails: set[str] = set()
    seen_keywords: set[str] = set()

    for s in strings:
        for url in _RE_URL.findall(s):
            if url not in seen_urls:
                categories["urls"].append(url)
                seen_urls.add(url)
        for ip in _RE_IP.findall(s):
            if ip not in seen_ips:
                categories["ip_addresses"].append(ip)
                seen_ips.add(ip)
        for email in _RE_EMAIL.findall(s):
            if email not in seen_emails:
                categories["emails"].append(email)
                seen_emails.add(email)
        s_lower = s.lower()
        for keyword in _SUSPICIOUS_KEYWORDS:
            if keyword.lower() in s_lower and s not in seen_keywords:
                categories["suspicious_keywords"].append(s[:200])
                seen_keywords.add(s)
                break

    return categories


class BinaryStringExtractorScanner(BaseOsintScanner):
    """Downloads a file from the target URL and extracts printable strings.

    Groups extracted strings into categories: URLs, IPs, emails, and entries
    containing suspicious security-relevant keywords. Useful for analysing
    compiled binaries, firmware, or obfuscated scripts (Module 95).
    """

    scanner_name = "binary_string_extractor"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400  # 24 hours — file content is stable

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = input_value.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"

        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            try:
                async with client.stream("GET", target) as resp:
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    content_length = int(resp.headers.get("content-length", 0))

                    chunks: list[bytes] = []
                    downloaded = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        chunks.append(chunk)
                        downloaded += len(chunk)
                        if downloaded >= _MAX_DOWNLOAD_BYTES:
                            log.warning("Download cap reached", url=target, bytes=downloaded)
                            break

                    data = b"".join(chunks)
            except httpx.HTTPStatusError as exc:
                return {
                    "target": target,
                    "found": False,
                    "error": f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}",
                }
            except httpx.RequestError as exc:
                return {"target": target, "found": False, "error": str(exc)}

        strings = _extract_strings(data)
        categories = _categorise_strings(strings)

        suspicious_count = len(categories["suspicious_keywords"])
        found = suspicious_count > 0 or len(categories["urls"]) > 0

        extracted_identifiers: list[str] = []
        for url in categories["urls"][:10]:
            extracted_identifiers.append(f"url:{url}")
        for ip in categories["ip_addresses"][:10]:
            extracted_identifiers.append(f"ip:{ip}")
        for email in categories["emails"][:10]:
            extracted_identifiers.append(f"email:{email}")

        return {
            "target": target,
            "found": found,
            "file_size_bytes": len(data),
            "content_type": content_type,
            "total_strings_extracted": len(strings),
            "url_count": len(categories["urls"]),
            "ip_count": len(categories["ip_addresses"]),
            "email_count": len(categories["emails"]),
            "suspicious_keyword_count": suspicious_count,
            "categories": categories,
            "extracted_identifiers": extracted_identifiers,
            "educational_note": (
                "The `strings` technique extracts printable character sequences from binary "
                "files, revealing embedded URLs, credentials, API keys, and configuration "
                "data that developers inadvertently compiled into binaries."
            ),
        }
