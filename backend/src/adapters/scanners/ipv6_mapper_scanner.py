"""IPv6 mapper scanner — discovers AAAA records and dual-stack configuration."""

import asyncio
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_COMMON_SUBDOMAINS = ["www", "mail", "ftp", "vpn", "api", "ns1", "ns2"]


async def _resolve_aaaa(hostname: str) -> list[str]:
    try:
        import dns.resolver
        answers = dns.resolver.resolve(hostname, "AAAA")
        return [str(rdata.address) for rdata in answers]
    except Exception:
        return []


class IPv6MapperScanner(BaseOsintScanner):
    """Discovers IPv6 addresses (AAAA records) and dual-stack presence for a domain."""

    scanner_name = "ipv6_mapper"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        all_hosts = [input_value] + [f"{sub}.{input_value}" for sub in _COMMON_SUBDOMAINS]

        tasks = [_resolve_aaaa(host) for host in all_hosts]
        results = await asyncio.gather(*tasks)

        ipv6_addresses: list[str] = []
        subdomains_with_ipv6: list[dict[str, Any]] = []

        for host, addrs in zip(all_hosts, results):
            if addrs:
                ipv6_addresses.extend(addrs)
                subdomains_with_ipv6.append({"subdomain": host, "ipv6_addresses": addrs})

        # Check dual-stack by also checking A records for the apex domain
        has_a_record = False
        try:
            import dns.resolver
            dns.resolver.resolve(input_value, "A")
            has_a_record = True
        except Exception:
            pass

        apex_ipv6 = results[0] if results else []
        dual_stack = has_a_record and len(apex_ipv6) > 0

        identifiers = [f"ip:{addr}" for addr in set(ipv6_addresses)]

        return {
            "domain": input_value,
            "found": len(ipv6_addresses) > 0,
            "ipv6_addresses": list(set(ipv6_addresses)),
            "dual_stack": dual_stack,
            "subdomains_with_ipv6": subdomains_with_ipv6,
            "extracted_identifiers": identifiers,
        }
