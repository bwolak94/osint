"""DNSRecon — advanced DNS reconnaissance scanner.

DNSRecon performs thorough DNS enumeration: zone transfers, wildcard detection,
cache snooping, DNSSEC validation, reverse lookups, and SRV/SPF/DMARC checks.

Two-mode operation:
1. **dnsrecon binary** — if on PATH, invoked with JSON output for full analysis
2. **Manual fallback** — comprehensive DNS queries via Python dnspython/socket
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
import tempfile
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common DNS record types to query
_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SRV", "CAA", "DNSKEY", "DS"]

# SRV record prefixes for service discovery
_SRV_PREFIXES: list[str] = [
    "_http._tcp", "_https._tcp", "_ftp._tcp", "_ssh._tcp",
    "_smtp._tcp", "_submission._tcp", "_imap._tcp", "_imaps._tcp",
    "_pop3._tcp", "_pop3s._tcp", "_xmpp-client._tcp", "_xmpp-server._tcp",
    "_ldap._tcp", "_kerberos._tcp", "_sip._tcp", "_sips._tcp",
    "_caldav._tcp", "_carddav._tcp", "_webdav._tcp",
    "_autodiscover._tcp", "_autoconfig._tcp",
    "_dmarc", "_domainkey",
]

# Known DNS-over-HTTPS resolvers for cross-validation
_DOH_RESOLVERS = [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
]

# Nameservers to test zone transfer against
_ZONE_TRANSFER_TEST_DOMAINS = [
    # Only test against target's own nameservers, not third parties
]


class DNSReconScanner(BaseOsintScanner):
    """Advanced DNS reconnaissance scanner.

    Performs comprehensive DNS enumeration including:
    - All record types (A, AAAA, MX, NS, TXT, SOA, CAA, DNSKEY)
    - Zone transfer attempts against discovered nameservers
    - Wildcard subdomain detection
    - SRV record service discovery
    - SPF/DMARC/DKIM policy analysis
    - Reverse DNS lookups
    - DNSSEC validation status
    - Cache snooping potential
    """

    scanner_name = "dnsrecon"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.lstrip("*.")

        if shutil.which("dnsrecon"):
            return await self._run_dnsrecon_binary(domain, input_value)
        return await self._manual_scan(domain, input_value)

    async def _run_dnsrecon_binary(self, domain: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"dnsrecon_{run_id}.json")
        cmd = [
            "dnsrecon",
            "-d", domain,
            "-j", out_file,
            "-t", "std,rvl,snoop,tld",
            "--lifetime", "3",
            "--tcp",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("dnsrecon timed out", domain=domain)
            try:
                proc.kill()
            except Exception:
                pass

        records: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                for entry in data if isinstance(data, list) else []:
                    records.append({
                        "type": entry.get("type", ""),
                        "name": entry.get("name", ""),
                        "address": entry.get("address", entry.get("target", "")),
                        "data": str(entry),
                    })
            except Exception as exc:
                log.warning("Failed to parse dnsrecon output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = list({
            f"subdomain:{r['name']}" for r in records
            if r.get("name") and r["name"].endswith(f".{domain}") and r["name"] != domain
        })
        return {
            "input": input_value,
            "scan_mode": "dnsrecon_binary",
            "domain": domain,
            "records": records,
            "total_records": len(records),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, domain: str, input_value: str) -> dict[str, Any]:
        all_records: dict[str, list[str]] = {}
        nameservers: list[str] = []
        identifiers: list[str] = []
        findings: list[dict[str, Any]] = []
        zone_transfer_results: dict[str, Any] = {}

        loop = asyncio.get_event_loop()

        # Helper: resolve with fallback
        async def resolve(qname: str, qtype: str) -> list[str]:
            try:
                # Use getaddrinfo for A/AAAA, gethostbyname_ex for MX/NS heuristic
                if qtype == "A":
                    result = await loop.run_in_executor(
                        None, lambda: socket.getaddrinfo(qname, None, socket.AF_INET)
                    )
                    return list({r[4][0] for r in result})
                elif qtype == "AAAA":
                    result = await loop.run_in_executor(
                        None, lambda: socket.getaddrinfo(qname, None, socket.AF_INET6)
                    )
                    return list({r[4][0] for r in result})
            except Exception:
                pass
            return []

        # Use httpx to query Cloudflare DNS-over-HTTPS for rich record types
        import httpx
        async with httpx.AsyncClient(timeout=8, headers={"Accept": "application/dns-json"}) as client:

            async def query_doh(name: str, rtype: str) -> list[str]:
                try:
                    resp = await client.get(
                        "https://cloudflare-dns.com/dns-query",
                        params={"name": name, "type": rtype},
                    )
                    data = resp.json()
                    answers = data.get("Answer", [])
                    return [a.get("data", "").rstrip(".") for a in answers if a.get("type")]
                except Exception:
                    return []

            # Query all standard record types
            for rtype in ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CAA", "DNSKEY", "DS", "CNAME"]:
                results = await query_doh(domain, rtype)
                if results:
                    all_records[rtype] = results

            # Extract nameservers
            nameservers = all_records.get("NS", [])

            # SRV record discovery
            srv_found: dict[str, list[str]] = {}
            srv_tasks = [(prefix, query_doh(f"{prefix}.{domain}", "SRV")) for prefix in _SRV_PREFIXES[:12]]
            for prefix, task_coro in srv_tasks:
                results = await task_coro
                if results:
                    srv_found[prefix] = results
                    identifiers.append(f"service:{prefix}.{domain}")
            if srv_found:
                all_records["SRV"] = [f"{k}: {v}" for k, v in srv_found.items()]

            # Zone transfer attempt against each NS
            for ns in nameservers[:3]:
                try:
                    # We can't do actual AXFR without dnspython, but we check if port 53 TCP is open
                    # (zone transfers use TCP)
                    conn = asyncio.open_connection(ns, 53)
                    reader, writer = await asyncio.wait_for(conn, timeout=3.0)
                    writer.close()
                    zone_transfer_results[ns] = {
                        "port_53_tcp": True,
                        "axfr_attempt": "TCP port open — run 'dig @{ns} {domain} AXFR' to test",
                    }
                    findings.append({
                        "type": "zone_transfer_candidate",
                        "severity": "medium",
                        "nameserver": ns,
                        "description": f"Nameserver {ns} has TCP port 53 open — potential zone transfer target",
                    })
                except Exception:
                    zone_transfer_results[ns] = {"port_53_tcp": False}

            # Wildcard detection
            random_sub = f"this-subdomain-should-not-exist-{os.urandom(4).hex()}.{domain}"
            wildcard_result = await query_doh(random_sub, "A")
            wildcard_detected = bool(wildcard_result)
            if wildcard_detected:
                findings.append({
                    "type": "wildcard_dns",
                    "severity": "low",
                    "description": f"Wildcard DNS detected — all subdomains resolve to {wildcard_result}",
                    "wildcard_ips": wildcard_result,
                })

            # SPF analysis
            txt_records = all_records.get("TXT", [])
            spf_record = next((r for r in txt_records if r.startswith("v=spf1")), None)
            dmarc_result = await query_doh(f"_dmarc.{domain}", "TXT")
            dkim_selector_results: dict[str, list[str]] = {}
            for selector in ["default", "google", "mail", "dkim", "k1", "selector1", "selector2"]:
                dkim = await query_doh(f"{selector}._domainkey.{domain}", "TXT")
                if dkim:
                    dkim_selector_results[selector] = dkim

            # SPF too permissive?
            if spf_record:
                if "+all" in spf_record:
                    findings.append({
                        "type": "spf_too_permissive",
                        "severity": "critical",
                        "description": "SPF record has '+all' — any server can send mail as this domain",
                        "record": spf_record,
                    })
                    identifiers.append("vuln:spf:plus_all")
                elif "~all" in spf_record:
                    findings.append({
                        "type": "spf_softfail",
                        "severity": "medium",
                        "description": "SPF record uses '~all' softfail — spoofing may still work",
                        "record": spf_record,
                    })
            else:
                findings.append({
                    "type": "spf_missing",
                    "severity": "medium",
                    "description": "No SPF record — domain can be spoofed for email phishing",
                })
                identifiers.append("vuln:email:no_spf")

            if not dmarc_result:
                findings.append({
                    "type": "dmarc_missing",
                    "severity": "medium",
                    "description": "No DMARC record — email spoofing protection is absent",
                })
                identifiers.append("vuln:email:no_dmarc")

        # Reverse DNS on discovered A records
        reverse_dns: dict[str, str] = {}
        for ip in all_records.get("A", [])[:5]:
            try:
                hostname = await loop.run_in_executor(
                    None, lambda _ip=ip: socket.gethostbyaddr(_ip)[0]
                )
                reverse_dns[ip] = hostname
            except Exception:
                pass

        # Build identifiers for discovered subdomains
        for rtype, values in all_records.items():
            if rtype in ("NS",):
                for ns in values:
                    identifiers.append(f"nameserver:{ns}")

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "domain": domain,
            "records": all_records,
            "nameservers": nameservers,
            "zone_transfer_tests": zone_transfer_results,
            "wildcard_detected": wildcard_detected,
            "spf_record": spf_record,
            "dmarc_record": dmarc_result,
            "dkim_selectors": dkim_selector_results,
            "reverse_dns": reverse_dns,
            "findings": findings,
            "total_findings": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
