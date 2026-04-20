"""DNS Brute-force Scanner — discovers subdomains via dictionary-based async DNS resolution.

Architecture:
- Uses Google DNS-over-HTTPS (DoH) exclusively to prevent local resolver leaks.
- Wildcard detection fires first to eliminate false positives (common on cloud CDNs).
- asyncio.Semaphore throttles concurrency to avoid triggering DNS-based rate limits.
- Results include resolved IPs and CNAME chains for each discovered subdomain.

Input entity:  DOMAIN (e.g. "example.com")
Output entities:
  - DOMAIN  — each discovered subdomain
  - IPv4Address — resolved A records
"""

from __future__ import annotations

import asyncio
import ipaddress
import random
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Embedded wordlist — top ~500 common subdomain prefixes
# Deliberately embedded to avoid filesystem dependency in containerised deploys.
# ---------------------------------------------------------------------------

_WORDLIST: list[str] = [
    # Core services
    "www", "mail", "email", "smtp", "pop", "pop3", "imap", "webmail", "mx", "mx1", "mx2",
    "ns", "ns1", "ns2", "ns3", "ns4", "dns", "dns1", "dns2",
    # Developer / DevOps
    "api", "api2", "api3", "v1", "v2", "v3", "rest", "graphql", "grpc",
    "dev", "develop", "developer", "development", "staging", "stage",
    "beta", "alpha", "preview", "demo", "sandbox", "test", "testing", "qa", "uat",
    "preprod", "pre", "prod", "production", "release",
    "ci", "cd", "jenkins", "travis", "gitlab", "github", "git", "svn",
    "docker", "registry", "k8s", "kubernetes", "harbor", "nexus", "artifactory",
    # Infrastructure
    "admin", "dashboard", "panel", "cpanel", "whm", "webdisk",
    "vpn", "remote", "rdp", "ssh", "bastion", "jump",
    "secure", "ssl", "tls", "auth", "sso", "oauth", "login", "account", "accounts",
    "id", "identity", "idp", "saml",
    "proxy", "gateway", "gw", "fw", "firewall", "lb", "haproxy", "nginx", "traefik",
    "cdn", "cdn1", "cdn2", "static", "static1", "static2", "assets", "assets1",
    "img", "img1", "img2", "images", "images1", "media", "video", "stream",
    "upload", "uploads", "files", "file", "download", "downloads", "s3", "storage",
    "backup", "backups", "archive", "archives",
    # Databases / Data
    "db", "database", "sql", "mysql", "pgsql", "postgres", "redis", "mongo",
    "es", "elastic", "elasticsearch", "solr", "cassandra",
    "analytics", "stats", "metrics", "prometheus", "grafana", "kibana",
    "log", "logs", "logging", "sentry", "sentry2", "apm", "trace",
    # Monitoring / Operations
    "monitor", "monitoring", "status", "health", "ping", "check",
    "ops", "operations", "infra", "infrastructure", "platform",
    "alertmanager", "pagerduty",
    # Collaboration / Communication
    "jira", "confluence", "wiki", "docs", "documentation", "help", "support", "kb",
    "chat", "slack", "teams", "meet", "video", "zoom", "webrtc",
    "forum", "community", "social", "blog", "news",
    "calendar", "cal", "events",
    # Commerce / Business
    "shop", "store", "cart", "checkout", "billing", "pay", "payments", "invoice",
    "portal", "customer", "client", "crm", "erp",
    "partner", "partners", "b2b", "extranet",
    "corp", "corporate", "enterprise", "intranet", "internal",
    # CDN / Cloud regions
    "us", "eu", "uk", "de", "fr", "nl", "sg", "ap", "ca", "au",
    "us-east", "us-west", "eu-west", "eu-central", "ap-east", "ap-south",
    "us1", "eu1", "ap1", "us2", "eu2",
    # Email infrastructure
    "smtp1", "smtp2", "smtp3", "relay", "mailer", "mailrelay",
    "bounce", "track", "tracking", "pixel", "open", "click",
    "newsletter", "lists", "listserv", "mailman", "sympa",
    "autodiscover", "autoconfig",
    # Office / Microsoft
    "owa", "exchange", "lync", "skype", "sharepoint",
    "outlook", "office", "o365", "azure",
    # Search / Content
    "search", "typesense", "meilisearch", "algolia",
    "content", "cms", "wordpress", "wp", "wp-admin",
    # Misc common
    "old", "legacy", "new", "v", "app", "apps", "mobile", "m",
    "ftp", "sftp", "webdav",
    "test1", "test2", "dev1", "dev2", "staging1", "staging2",
    "api-dev", "api-staging", "api-prod",
    "backend", "frontend", "fe", "be",
    "internal", "private", "secret",
    "mgmt", "management", "control",
    "relay1", "relay2",
    "web", "web1", "web2", "web3",
    "node", "node1", "node2",
    "server", "server1", "server2",
    "edge", "edge1", "edge2",
    "push", "socket", "ws", "wss",
    "cron", "worker", "queue",
    "minio", "kafka", "rabbitmq", "celery",
    "ldap", "ad", "directory",
    "ca", "pki", "ocsp", "crl",
]


class DNSBruteforceScanner(BaseOsintScanner):
    """Discovers subdomains via async dictionary-based DNS brute-force.

    Input:  ScanInputType.DOMAIN
    Output: discovered subdomains → domain: and ip: identifiers

    Notes:
    - DoH endpoint: Google (8.8.8.8) via HTTPS — no local resolver leaks.
    - Wildcard detection: probes a random non-existent prefix; if it resolves,
      all matching IPs are treated as wildcard and filtered from results.
    - Concurrency capped at MAX_CONCURRENCY via asyncio.Semaphore.
    """

    scanner_name = "dns_bruteforce"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 21600  # 6 hours

    DOH_URL = "https://dns.google/resolve"
    MAX_CONCURRENCY = 40

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.lower().strip().rstrip(".")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8.0),
            headers={"Accept": "application/dns-json"},
        ) as client:
            # Step 1: Wildcard detection
            wildcard_ips = await self._detect_wildcard(client, domain)
            if wildcard_ips:
                log.info("Wildcard DNS detected", domain=domain, wildcard_ips=sorted(wildcard_ips))

            # Step 2: Parallel brute-force
            semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)
            tasks = [
                self._resolve_subdomain(client, semaphore, f"{prefix}.{domain}", wildcard_ips)
                for prefix in _WORDLIST
            ]
            raw_results = await asyncio.gather(*tasks, return_exceptions=False)

        discovered: list[dict[str, Any]] = [r for r in raw_results if r is not None]
        discovered.sort(key=lambda r: r["subdomain"])

        all_ips: set[str] = set()
        for r in discovered:
            all_ips.update(r.get("ips", []))

        identifiers: list[str] = (
            [f"domain:{r['subdomain']}" for r in discovered]
            + [f"ip:{ip}" for ip in sorted(all_ips)]
        )

        return {
            "domain": domain,
            "found": bool(discovered),
            "wildcard_detected": bool(wildcard_ips),
            "wildcard_ips": sorted(wildcard_ips),
            "discovered_count": len(discovered),
            "subdomains": discovered,
            "wordlist_size": len(_WORDLIST),
            "source": "dns_bruteforce_doh",
            "extracted_identifiers": identifiers,
        }

    async def _detect_wildcard(self, client: httpx.AsyncClient, domain: str) -> set[str]:
        """Resolve a random non-existent subdomain to detect wildcard DNS."""
        probe = f"osint-wc-{random.randint(10_000_000, 99_999_999)}.{domain}"
        ips = await self._query_a(client, probe)
        return set(ips)

    async def _resolve_subdomain(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        fqdn: str,
        wildcard_ips: set[str],
    ) -> dict[str, Any] | None:
        """Resolve one FQDN and return a result dict or None if not found."""
        async with semaphore:
            a_records = await self._query_a(client, fqdn)
            cname_records = await self._query_cname(client, fqdn)

            # Filter wildcard IPs
            real_ips = [ip for ip in a_records if ip not in wildcard_ips]

            if not real_ips and not cname_records:
                return None

            # Validate IPs are actually parseable
            valid_ips: list[str] = []
            for ip in real_ips:
                try:
                    ipaddress.ip_address(ip)
                    valid_ips.append(ip)
                except ValueError:
                    pass

            record: dict[str, Any] = {"subdomain": fqdn, "ips": valid_ips}
            if cname_records:
                record["cname"] = cname_records[0]
            return record

    async def _query_a(self, client: httpx.AsyncClient, name: str) -> list[str]:
        return await self._query_doh(client, name, "A", dns_type=1)

    async def _query_cname(self, client: httpx.AsyncClient, name: str) -> list[str]:
        return await self._query_doh(client, name, "CNAME", dns_type=5)

    async def _query_doh(
        self, client: httpx.AsyncClient, name: str, rtype: str, dns_type: int
    ) -> list[str]:
        """Query Google DoH and return answer data strings for the given record type."""
        try:
            resp = await client.get(self.DOH_URL, params={"name": name, "type": rtype})
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                str(ans["data"]).rstrip(".")
                for ans in data.get("Answer", [])
                if ans.get("type") == dns_type
            ]
        except Exception:
            return []

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
