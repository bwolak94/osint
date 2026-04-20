"""Comprehensive DNS record resolution scanner using dnspython."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class DnsxScanner(BaseOsintScanner):
    scanner_name = "dnsx"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if input_type == ScanInputType.IP_ADDRESS:
            return await self._scan_ip(input_value)
        return await self._scan_domain(input_value)

    async def _scan_domain(self, domain: str) -> dict[str, Any]:
        try:
            import dns.resolver
            import dns.reversename
        except ImportError as exc:
            return {
                "input": domain,
                "found": False,
                "error": "dnspython not installed",
                "extracted_identifiers": [],
            }

        records: dict[str, list[str]] = {}
        resolved_ips: list[str] = []
        mx_servers: list[str] = []
        nameservers: list[str] = []
        txt_records: list[str] = []
        ptr_records: list[str] = []

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 10

        record_types = ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CNAME", "CAA"]

        loop = asyncio.get_running_loop()

        for rtype in record_types:
            try:
                answers = await loop.run_in_executor(
                    None, lambda rt=rtype: resolver.resolve(domain, rt)
                )
                values: list[str] = []
                for rdata in answers:
                    val = _rdata_to_str(rdata, rtype)
                    values.append(val)
                    if rtype == "A":
                        resolved_ips.append(val)
                    elif rtype == "AAAA":
                        resolved_ips.append(val)
                    elif rtype == "MX":
                        mx_host = str(rdata.exchange).rstrip(".")
                        mx_servers.append(mx_host)
                    elif rtype == "NS":
                        ns_host = str(rdata.target).rstrip(".")
                        nameservers.append(ns_host)
                    elif rtype == "TXT":
                        txt_records.append(val)
                records[rtype] = values
            except Exception:
                pass

        # PTR lookups for resolved IPs
        for ip in resolved_ips:
            try:
                rev = dns.reversename.from_address(ip)
                ptr_answers = await loop.run_in_executor(
                    None, lambda r=rev: resolver.resolve(r, "PTR")
                )
                for rdata in ptr_answers:
                    ptr_records.append(str(rdata.target).rstrip("."))
            except Exception:
                pass

        # DNSSEC validation check
        has_dnssec = await _check_dnssec(loop, resolver, domain)

        identifiers: list[str] = []
        for ip in resolved_ips:
            identifiers.append(f"ip:{ip}")
        for mx in mx_servers:
            identifiers.append(f"domain:{mx}")
        for ns in nameservers:
            identifiers.append(f"domain:{ns}")

        return {
            "input": domain,
            "found": bool(records),
            "records": records,
            "resolved_ips": list(dict.fromkeys(resolved_ips)),
            "mx_servers": list(dict.fromkeys(mx_servers)),
            "nameservers": list(dict.fromkeys(nameservers)),
            "txt_records": txt_records,
            "has_dnssec": has_dnssec,
            "ptr_records": ptr_records,
            "extracted_identifiers": list(dict.fromkeys(identifiers)),
        }

    async def _scan_ip(self, ip: str) -> dict[str, Any]:
        try:
            import dns.resolver
            import dns.reversename
        except ImportError:
            return {
                "input": ip,
                "found": False,
                "error": "dnspython not installed",
                "extracted_identifiers": [],
            }

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 10
        loop = asyncio.get_running_loop()
        ptr_records: list[str] = []

        try:
            rev = dns.reversename.from_address(ip)
            ptr_answers = await loop.run_in_executor(
                None, lambda: resolver.resolve(rev, "PTR")
            )
            for rdata in ptr_answers:
                ptr_records.append(str(rdata.target).rstrip("."))
        except Exception as exc:
            log.debug("PTR lookup failed", ip=ip, error=str(exc))

        identifiers = [f"domain:{ptr}" for ptr in ptr_records]

        return {
            "input": ip,
            "found": bool(ptr_records),
            "ptr_records": ptr_records,
            "records": {"PTR": ptr_records},
            "resolved_ips": [],
            "mx_servers": [],
            "nameservers": [],
            "txt_records": [],
            "has_dnssec": False,
            "extracted_identifiers": identifiers,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rdata_to_str(rdata: Any, rtype: str) -> str:
    """Convert a dns.rdata object to a human-readable string."""
    if rtype in ("A", "AAAA"):
        return str(rdata.address)
    if rtype == "MX":
        return f"{rdata.preference} {str(rdata.exchange).rstrip('.')}"
    if rtype == "NS":
        return str(rdata.target).rstrip(".")
    if rtype == "TXT":
        return " ".join(part.decode("utf-8", errors="replace") for part in rdata.strings)
    if rtype == "SOA":
        return (
            f"{str(rdata.mname).rstrip('.')} {str(rdata.rname).rstrip('.')} "
            f"{rdata.serial} {rdata.refresh} {rdata.retry} {rdata.expire} {rdata.minimum}"
        )
    if rtype == "CNAME":
        return str(rdata.target).rstrip(".")
    if rtype == "CAA":
        return f"{rdata.flags} {rdata.tag.decode()} {rdata.value.decode()}"
    return str(rdata)


async def _check_dnssec(loop: asyncio.AbstractEventLoop, resolver: Any, domain: str) -> bool:
    try:
        import dns.rdatatype
        answers = await loop.run_in_executor(
            None, lambda: resolver.resolve(domain, "DNSKEY")
        )
        return bool(answers)
    except Exception:
        return False
