"""Email header scanner — parses RFC 5322 headers to trace relay hops and extract IOCs."""

import email
import email.policy
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20

# Matches IPv4 addresses enclosed in square brackets inside Received headers
_IP_BRACKET_RE = re.compile(r"\[(\d{1,3}(?:\.\d{1,3}){3})\]")
# RFC 5321 simple email address extraction
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Known private/loopback ranges we want to exclude from identifiers
_PRIVATE_PREFIXES = (
    "10.",
    "192.168.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "127.",
)


def _is_public_ip(ip: str) -> bool:
    return not any(ip.startswith(prefix) for prefix in _PRIVATE_PREFIXES)


def _parse_headers(raw: str) -> dict[str, Any]:
    """Parse raw RFC 5322 message headers and extract forensic artefacts."""
    msg = email.message_from_string(raw, policy=email.policy.default)

    # --- Relay hops from Received headers ----------------------------------
    relay_ips: list[str] = []
    received_headers: list[str] = msg.get_all("received") or []
    for received in received_headers:
        for ip in _IP_BRACKET_RE.findall(received):
            if _is_public_ip(ip) and ip not in relay_ips:
                relay_ips.append(ip)

    # --- X-Originating-IP ---------------------------------------------------
    originating_ip: str | None = msg.get("x-originating-ip")
    if originating_ip:
        originating_ip = originating_ip.strip().strip("[]")
        if _is_public_ip(originating_ip) and originating_ip not in relay_ips:
            relay_ips.insert(0, originating_ip)

    # --- Authentication results (SPF / DKIM / DMARC) -----------------------
    auth_results: str = msg.get("authentication-results", "") or msg.get("arc-authentication-results", "")
    spf_result: str | None = None
    dkim_result: str | None = None
    dmarc_result: str | None = None

    if auth_results:
        spf_match = re.search(r"spf=(\S+)", auth_results, re.IGNORECASE)
        dkim_match = re.search(r"dkim=(\S+)", auth_results, re.IGNORECASE)
        dmarc_match = re.search(r"dmarc=(\S+)", auth_results, re.IGNORECASE)
        spf_result = spf_match.group(1).rstrip(";") if spf_match else None
        dkim_result = dkim_match.group(1).rstrip(";") if dkim_match else None
        dmarc_result = dmarc_match.group(1).rstrip(";") if dmarc_match else None

    # --- Email addresses ----------------------------------------------------
    reply_to_raw: str = msg.get("reply-to", "") or ""
    return_path_raw: str = msg.get("return-path", "") or ""
    from_raw: str = msg.get("from", "") or ""
    to_raw: str = msg.get("to", "") or ""

    reply_to_addresses = _EMAIL_RE.findall(reply_to_raw)
    return_path_addresses = _EMAIL_RE.findall(return_path_raw)
    from_addresses = _EMAIL_RE.findall(from_raw)

    # Suspicious: reply-to differs from from address
    reply_to_mismatch = bool(
        reply_to_addresses
        and from_addresses
        and not any(rt in from_addresses for rt in reply_to_addresses)
    )

    subject: str = str(msg.get("subject", "")) or ""
    message_id: str = str(msg.get("message-id", "")) or ""
    date_sent: str = str(msg.get("date", "")) or ""

    all_email_addresses = list(
        {*reply_to_addresses, *return_path_addresses}
    )

    identifiers: list[str] = (
        [f"ip:{ip}" for ip in relay_ips]
        + [f"email:{addr}" for addr in all_email_addresses]
    )

    return {
        "found": True,
        "relay_ips": relay_ips,
        "relay_hop_count": len(received_headers),
        "originating_ip": originating_ip,
        "spf_result": spf_result,
        "dkim_result": dkim_result,
        "dmarc_result": dmarc_result,
        "reply_to": reply_to_addresses,
        "return_path": return_path_addresses,
        "from_addresses": from_addresses,
        "reply_to_mismatch": reply_to_mismatch,
        "subject": subject,
        "message_id": message_id,
        "date_sent": date_sent,
        "extracted_identifiers": identifiers,
    }


class EmailHeaderScanner(BaseOsintScanner):
    """Fetches a raw .eml file from a URL and parses its headers to extract
    relay IPs, authentication results, and suspicious address mismatches."""

    scanner_name = "email_headers"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            raw_content = await self._fetch_raw_email(client, input_value)

        if raw_content is None:
            return {
                "input_url": input_value,
                "found": False,
                "error": "Could not fetch email content from the provided URL",
                "extracted_identifiers": [],
            }

        parsed = _parse_headers(raw_content)
        parsed["input_url"] = input_value
        log.info(
            "Email headers parsed",
            url=input_value,
            relay_ips=parsed.get("relay_ips"),
            spf=parsed.get("spf_result"),
            dkim=parsed.get("dkim_result"),
        )
        return parsed

    async def _fetch_raw_email(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Download the raw email content from the given URL."""
        try:
            resp = await client.get(url)

            if resp.status_code == 429:
                raise RateLimitError("Rate limited fetching email content")
            if resp.status_code != 200:
                log.warning("Failed to fetch email URL", url=url, status=resp.status_code)
                return None

            return resp.text

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("Email fetch failed", url=url, error=str(exc))
            return None
