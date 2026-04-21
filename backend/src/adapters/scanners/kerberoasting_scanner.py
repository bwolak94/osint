"""Kerberoasting Toolkit — passive DNS-based discovery of potential Kerberos SPN accounts.

Module 111 in the Infrastructure & Exploitation domain. Performs passive DNS enumeration
to identify service records that match common Kerberos Service Principal Name (SPN)
patterns. Kerberoasting is an Active Directory attack that targets service accounts
with SPNs; their TGS tickets can be requested by any domain user and cracked offline.
This scanner performs only passive DNS recon — no LDAP or Kerberos traffic is generated.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common service prefixes used in Kerberos SPNs
_SPN_SERVICE_PREFIXES = [
    "http",
    "host",
    "ldap",
    "mssql",
    "MSSQLSvc",
    "SMTP",
    "POP3",
    "IMAP",
    "FTP",
    "DNS",
    "NFS",
    "wsman",
    "termsrv",
    "cifs",
    "rpc",
    "gc",
    "exchangeMDB",
    "exchangeRFR",
    "exchangeAB",
    "w3svc",
    "MSServerClusterMgmtAPI",
]

# Common SPN hostname patterns to probe via DNS
_SPN_HOST_PATTERNS = [
    "dc",
    "dc01",
    "dc02",
    "adfs",
    "mail",
    "exchange",
    "smtp",
    "mssql",
    "sql",
    "sqlserver",
    "sharepoint",
    "lync",
    "skype",
    "wsman",
    "sccm",
    "scom",
    "rdp",
    "rdweb",
    "vpn",
    "fs",
    "sts",
]

_SRV_RECORDS = [
    "_kerberos._tcp",
    "_kerberos._udp",
    "_kpasswd._tcp",
    "_ldap._tcp",
    "_ldap._tcp.dc._msdcs",
    "_kerberos._tcp.dc._msdcs",
    "_gc._tcp",
    "_gc._tcp.dc._msdcs",
]


def _resolve_host(hostname: str) -> str | None:
    """Try to resolve a hostname to an IP; return None if it fails."""
    try:
        return socket.gethostbyname(hostname)
    except (socket.gaierror, OSError):
        return None


def _check_srv_record(domain: str, srv_prefix: str) -> dict[str, Any] | None:
    """Attempt to resolve a SRV record for a known Kerberos service prefix."""
    fqdn = f"{srv_prefix}.{domain}"
    try:
        import dns.resolver  # type: ignore[import-untyped]
        answers = dns.resolver.resolve(fqdn, "SRV")
        targets = [str(a.target).rstrip(".") for a in answers]
        return {
            "srv_record": fqdn,
            "type": "SRV",
            "targets": targets,
            "significance": "Kerberos/AD service record — confirms Active Directory presence",
        }
    except Exception:
        pass
    return None


class KerberoastingScanner(BaseOsintScanner):
    """Performs passive DNS recon to identify potential Kerberos SPN patterns.

    Resolves common SPN-related hostnames and SRV records for the target domain
    to identify Active Directory infrastructure. Returns potential SPNs with
    educational context about Kerberoasting and offline hash cracking (Module 111).
    No LDAP queries, Kerberos traffic, or authentication is attempted.
    """

    scanner_name = "kerberoasting_scanner"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower().lstrip("www.").split("/")[0]

        resolved_hosts: list[dict[str, Any]] = []
        srv_records: list[dict[str, Any]] = []
        potential_spns: list[str] = []

        # Resolve common SPN host patterns in thread pool (socket is blocking)
        loop = asyncio.get_event_loop()

        async def resolve_pattern(prefix: str) -> dict[str, Any] | None:
            hostname = f"{prefix}.{domain}"
            ip = await loop.run_in_executor(None, _resolve_host, hostname)
            if ip:
                return {"hostname": hostname, "ip": ip, "pattern": prefix}
            return None

        resolve_tasks = [resolve_pattern(prefix) for prefix in _SPN_HOST_PATTERNS]
        resolve_results = await asyncio.gather(*resolve_tasks, return_exceptions=True)
        for result in resolve_results:
            if isinstance(result, dict):
                resolved_hosts.append(result)
                # Generate potential SPNs for this host
                for svc in _SPN_SERVICE_PREFIXES[:5]:
                    potential_spns.append(f"{svc}/{result['hostname']}:PORT")
                    potential_spns.append(f"{svc}/{result['hostname']}")

        # Check SRV records (synchronous DNS, run in executor)
        async def check_srv(srv_prefix: str) -> dict[str, Any] | None:
            return await loop.run_in_executor(None, _check_srv_record, domain, srv_prefix)

        srv_tasks = [check_srv(srv) for srv in _SRV_RECORDS]
        srv_results = await asyncio.gather(*srv_tasks, return_exceptions=True)
        for result in srv_results:
            if isinstance(result, dict):
                srv_records.append(result)

        ad_infrastructure_detected = len(srv_records) > 0 or len(resolved_hosts) > 0

        return {
            "target": domain,
            "found": ad_infrastructure_detected,
            "ad_infrastructure_detected": ad_infrastructure_detected,
            "resolved_hosts": resolved_hosts,
            "srv_records": srv_records,
            "potential_spns": list(dict.fromkeys(potential_spns))[:40],
            "severity": "Medium" if ad_infrastructure_detected else "None",
            "educational_info": {
                "attack": "Kerberoasting",
                "description": (
                    "Kerberoasting extracts Kerberos TGS tickets for service accounts with SPNs. "
                    "Any authenticated domain user can request these tickets without special privileges. "
                    "The ticket is encrypted with the service account's NTLM hash and can be cracked offline."
                ),
                "tools": ["Impacket GetUserSPNs.py", "Rubeus", "PowerView"],
                "hash_format": "$krb5tgs$23$*<user>$<realm>$<spn>*$<hash>",
                "mitigation": [
                    "Use Managed Service Accounts (MSA/gMSA) for service accounts.",
                    "Enforce long (>25 char), random passwords for SPN-linked accounts.",
                    "Enable AES encryption for Kerberos (prevents RC4 downgrade).",
                    "Monitor for TGS ticket requests in Windows Security Event 4769.",
                ],
            },
        }
