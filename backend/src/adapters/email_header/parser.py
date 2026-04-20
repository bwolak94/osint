"""Email header parser — extracts routing path, auth results, and originating IP."""

from __future__ import annotations

import email
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hop:
    """One SMTP relay hop extracted from Received headers."""
    index: int
    from_host: str | None = None
    by_host: str | None = None
    ip: str | None = None
    timestamp: str | None = None
    protocol: str | None = None
    delay_seconds: int | None = None


@dataclass
class ParsedEmailHeaders:
    subject: str | None = None
    sender_from: str | None = None
    sender_reply_to: str | None = None
    message_id: str | None = None
    date: str | None = None
    originating_ip: str | None = None
    spf_result: str | None = None
    dkim_result: str | None = None
    dmarc_result: str | None = None
    is_spoofed: bool = False
    hops: list[Hop] = field(default_factory=list)
    raw_headers_summary: dict[str, Any] = field(default_factory=dict)


_IP_RE = re.compile(
    r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]"
    r"|(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)

_AUTH_PASS_RE = re.compile(r"(spf|dkim|dmarc)=(\w+)", re.IGNORECASE)

_PRIVATE_IP_PREFIXES = (
    "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
    "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
    "172.29.", "172.30.", "172.31.", "192.168.", "127.", "::1", "fe80:",
)


def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_IP_PREFIXES)


class EmailHeaderParser:
    """Pure-Python email header parser using stdlib `email` module."""

    def parse(self, raw_headers: str) -> ParsedEmailHeaders:
        """Parse raw email headers string and return structured data."""
        msg = email.message_from_string(raw_headers)

        result = ParsedEmailHeaders(
            subject=msg.get("Subject"),
            sender_from=msg.get("From"),
            sender_reply_to=msg.get("Reply-To"),
            message_id=msg.get("Message-ID"),
            date=msg.get("Date"),
        )

        # Collect all header values for summary
        result.raw_headers_summary = {
            k: msg.get(k, "") for k in set(k.lower() for k in msg.keys())
            if k.lower() in {
                "from", "to", "cc", "reply-to", "subject", "date", "message-id",
                "x-originating-ip", "x-mailer", "x-spam-status", "user-agent",
                "mime-version", "content-type",
            }
        }

        # Parse Authentication-Results header
        auth_results = msg.get_all("Authentication-Results") or []
        for ar in auth_results:
            for match in _AUTH_PASS_RE.finditer(ar):
                proto, result_val = match.group(1).lower(), match.group(2).lower()
                if proto == "spf":
                    result.spf_result = result_val
                elif proto == "dkim":
                    result.dkim_result = result_val
                elif proto == "dmarc":
                    result.dmarc_result = result_val

        # Parse X-Originating-IP
        x_orig_ip = msg.get("X-Originating-IP", "").strip("[] ")
        if x_orig_ip and not _is_private(x_orig_ip):
            result.originating_ip = x_orig_ip

        # Parse Received headers (oldest hop last in email)
        received_headers = list(reversed(msg.get_all("Received") or []))
        for i, received in enumerate(received_headers):
            hop = self._parse_received(i, received)
            result.hops.append(hop)
            # Originating IP = first external IP in chain
            if result.originating_ip is None and hop.ip and not _is_private(hop.ip):
                result.originating_ip = hop.ip

        # Spoofing heuristic: SPF fail + DKIM fail
        result.is_spoofed = (
            result.spf_result in ("fail", "softfail", "none") and
            result.dkim_result in ("fail", "none", None)
        )

        return result

    def _parse_received(self, index: int, header_value: str) -> Hop:
        """Extract key fields from a single Received header."""
        hop = Hop(index=index)

        # Extract IP addresses
        ips = _IP_RE.findall(header_value)
        for bracketed, plain in ips:
            ip = bracketed or plain
            if ip and not _is_private(ip):
                hop.ip = ip
                break
        if hop.ip is None:
            for bracketed, plain in ips:
                ip = bracketed or plain
                if ip:
                    hop.ip = ip
                    break

        # Extract from/by
        from_match = re.search(r"\bfrom\s+([\w.\-\[\]]+)", header_value, re.IGNORECASE)
        if from_match:
            hop.from_host = from_match.group(1)

        by_match = re.search(r"\bby\s+([\w.\-]+)", header_value, re.IGNORECASE)
        if by_match:
            hop.by_host = by_match.group(1)

        # Extract protocol
        with_match = re.search(r"\bwith\s+(\w+)", header_value, re.IGNORECASE)
        if with_match:
            hop.protocol = with_match.group(1).upper()

        return hop
