"""Gobuster — DNS subdomain and vhost discovery scanner.

Gobuster is a tool for brute-forcing URIs, DNS subdomains, and virtual hosts.
Its DNS and vhost modes complement feroxbuster's directory mode.

Two-mode operation:
1. **gobuster binary** — if on PATH, invoked in dns/vhost mode
2. **Manual fallback** — async DNS brute-force + vhost header probing
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Subdomain wordlist — extended beyond basic dns_bruteforce_scanner
_SUBDOMAIN_WORDLIST: list[str] = [
    # Infrastructure
    "www", "mail", "ftp", "smtp", "pop", "imap", "ns1", "ns2", "ns3",
    "mx", "mx1", "mx2", "vpn", "ssh", "sftp", "api", "cdn", "static",
    # Dev/staging
    "dev", "develop", "development", "staging", "stage", "stg", "test",
    "testing", "qa", "uat", "preprod", "preview", "demo", "sandbox",
    "beta", "alpha", "rc", "release", "canary",
    # Admin
    "admin", "administrator", "manage", "manager", "panel", "portal",
    "control", "dashboard", "backend", "backoffice", "cpanel", "whm",
    # Apps
    "app", "apps", "mobile", "m", "wap", "web", "www2", "new",
    "old", "legacy", "classic", "v1", "v2", "v3",
    # Services
    "blog", "shop", "store", "pay", "payment", "checkout", "cart",
    "support", "help", "docs", "doc", "documentation", "wiki",
    "forum", "community", "chat", "status", "monitor",
    # Auth
    "auth", "login", "sso", "oauth", "account", "accounts", "id",
    "identity", "access",
    # Internal / infra
    "internal", "intranet", "private", "corp", "corporate",
    "office", "remote", "git", "gitlab", "github", "jenkins",
    "ci", "cd", "build", "deploy", "registry", "docker", "k8s",
    "kubernetes", "grafana", "kibana", "elk", "elastic", "redis",
    "db", "database", "mysql", "postgres", "mongo",
    # Cloud
    "aws", "azure", "gcp", "cloud", "s3", "bucket",
    # Security
    "security", "sec", "waf", "firewall", "proxy", "gateway",
    # Monitoring
    "metrics", "logs", "logging", "trace", "apm", "splunk",
    # Customer-facing
    "customer", "client", "partner", "vendor", "supplier",
    "reseller", "affiliate", "api2", "apiv2", "apiv1",
]

# Common virtual host name patterns
_VHOST_PATTERNS: list[str] = [
    "dev", "staging", "test", "admin", "api", "beta", "internal",
    "preprod", "demo", "app", "portal", "shop", "mail",
]


class GobusterScanner(BaseOsintScanner):
    """DNS subdomain and virtual host brute-force scanner.

    Discovers subdomains via DNS resolution and virtual hosts via HTTP
    Host header manipulation. Complements passive subdomain discovery
    with active brute-force enumeration.
    """

    scanner_name = "gobuster"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.lstrip("*.")

        if shutil.which("gobuster"):
            return await self._run_gobuster_binary(domain, input_value)
        return await self._manual_scan(domain, input_value)

    async def _run_gobuster_binary(self, domain: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"gobuster_{run_id}.txt")
        wordlist_file = os.path.join(tempfile.gettempdir(), f"gobuster_wl_{run_id}.txt")

        try:
            with open(wordlist_file, "w") as f:
                f.write("\n".join(_SUBDOMAIN_WORDLIST))

            cmd = [
                "gobuster", "dns",
                "-d", domain,
                "-w", wordlist_file,
                "-o", out_file,
                "-q",
                "--no-color",
                "-t", "20",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("gobuster timed out", domain=domain)
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            try:
                os.unlink(wordlist_file)
            except OSError:
                pass

        subdomains: list[str] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    for line in fh:
                        line = line.strip()
                        if line and not line.startswith("="):
                            # Extract subdomain from gobuster output
                            m = re.search(r"Found: (\S+)", line)
                            if m:
                                subdomains.append(m.group(1))
                            elif "." in line:
                                subdomains.append(line)
            except Exception as exc:
                log.warning("Failed to read gobuster output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"subdomain:{s}" for s in subdomains]
        return {
            "input": input_value,
            "scan_mode": "gobuster_binary",
            "domain": domain,
            "subdomains": subdomains,
            "total_subdomains": len(subdomains),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, domain: str, input_value: str) -> dict[str, Any]:
        resolved_subdomains: list[dict[str, Any]] = []
        vhosts_found: list[dict[str, Any]] = []
        identifiers: list[str] = []

        loop = asyncio.get_event_loop()
        semaphore = asyncio.Semaphore(30)

        # Get baseline IP for vhost detection
        try:
            base_ip = await loop.run_in_executor(None, lambda: socket.gethostbyname(domain))
        except Exception:
            base_ip = None

        # Phase 1: DNS brute-force
        async def resolve_subdomain(subdomain: str) -> None:
            async with semaphore:
                fqdn = f"{subdomain}.{domain}"
                try:
                    addrs = await loop.run_in_executor(
                        None,
                        lambda: socket.getaddrinfo(fqdn, None, socket.AF_INET),
                    )
                    if addrs:
                        ip = addrs[0][4][0]
                        resolved_subdomains.append({
                            "subdomain": fqdn,
                            "ip": ip,
                            "cname": None,
                        })
                        identifiers.append(f"subdomain:{fqdn}")
                except (socket.gaierror, socket.herror, OSError):
                    pass

        dns_tasks = [resolve_subdomain(s) for s in _SUBDOMAIN_WORDLIST]
        await asyncio.gather(*dns_tasks)

        # Phase 2: Virtual host detection via Host header manipulation
        if base_ip:
            async with httpx.AsyncClient(
                timeout=5,
                follow_redirects=False,
                verify=False,
                headers={"User-Agent": "Mozilla/5.0 (compatible; VHostScanner/1.0)"},
            ) as client:
                try:
                    baseline_resp = await client.get(
                        f"https://{domain}",
                        headers={"Host": domain},
                    )
                    baseline_len = len(baseline_resp.content)
                except Exception:
                    baseline_len = 0

                async def check_vhost(vhost: str) -> None:
                    async with semaphore:
                        test_host = f"{vhost}.{domain}"
                        try:
                            resp = await client.get(
                                f"https://{domain}",
                                headers={"Host": test_host},
                            )
                            if resp.status_code not in (400, 421, 444) and \
                               abs(len(resp.content) - baseline_len) > 100:
                                vhosts_found.append({
                                    "vhost": test_host,
                                    "status_code": resp.status_code,
                                    "content_length": len(resp.content),
                                })
                                ident = f"vhost:{test_host}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                        except Exception:
                            pass

                vhost_tasks = [check_vhost(v) for v in _VHOST_PATTERNS]
                await asyncio.gather(*vhost_tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "domain": domain,
            "subdomains": resolved_subdomains,
            "total_subdomains": len(resolved_subdomains),
            "virtual_hosts": vhosts_found,
            "total_vhosts": len(vhosts_found),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
