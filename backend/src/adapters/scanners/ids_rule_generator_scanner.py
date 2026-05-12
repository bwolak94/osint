"""IDS Rule Generator — generates Snort/Suricata detection rules from target observations.

Module 99 in the Infrastructure & Exploitation domain. Probes the target IP or domain,
analyses observed HTTP headers, service banners, open ports, and response patterns,
then generates ready-to-use Snort/Suricata IDS rules that would detect traffic to
or from this target. Educational tool for understanding network intrusion detection.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_COMMON_PORTS = [80, 443, 8080, 8443, 22, 21, 25, 3306, 5432]
_SERVER_HEADER_RE = re.compile(r"([A-Za-z\-]+)/(\d+[\.\d]*)", re.IGNORECASE)


def _normalize_target(input_value: str) -> tuple[str, str]:
    """Return (host, base_url) tuple from domain or IP."""
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    host = parsed.hostname or parsed.netloc.split(":")[0]
    return host, f"{parsed.scheme}://{parsed.netloc}"


def _resolve_ip(host: str) -> str | None:
    try:
        return socket.gethostbyname(host)
    except (socket.gaierror, OSError):
        return None


def _generate_sid() -> int:
    """Generate a stable rule SID in the 9000000+ range (custom/local rules)."""
    import time
    return 9000000 + int(time.time()) % 1000000


def _build_http_header_rule(
    sid: int,
    target_ip: str,
    header_name: str,
    header_value: str,
    description: str,
) -> str:
    """Build a Snort/Suricata rule matching an HTTP response header pattern."""
    safe_value = header_value.replace('"', '\\"')[:50]
    return (
        f'alert http $HOME_NET any -> {target_ip} $HTTP_PORTS '
        f'(msg:"OSINT-RESEARCH {description}"; '
        f'flow:established,to_server; '
        f'http.response_body; '
        f'http.header; content:"{header_name}: {safe_value}"; '
        f'sid:{sid}; rev:1; '
        f'metadata:created_at 2025-01-01, confidence medium;)'
    )


def _build_port_rule(sid: int, target_ip: str, port: int, protocol: str, description: str) -> str:
    """Build a Snort/Suricata rule for traffic to a specific port."""
    return (
        f"alert {protocol} $HOME_NET any -> {target_ip} {port} "
        f'(msg:"OSINT-RESEARCH {description}"; '
        f"flow:established,to_server; "
        f"flags:S; "
        f"sid:{sid}; rev:1; "
        f"metadata:created_at 2025-01-01, confidence high;)"
    )


def _build_dns_rule(sid: int, domain: str) -> str:
    """Build a Suricata rule matching DNS queries for the target domain."""
    return (
        f'alert dns $HOME_NET any -> any 53 '
        f'(msg:"OSINT-RESEARCH DNS lookup for {domain}"; '
        f'dns.query; content:"{domain}"; nocase; '
        f"sid:{sid}; rev:1; "
        f"metadata:created_at 2025-01-01, confidence high;)"
    )


class IDSRuleGeneratorScanner(BaseOsintScanner):
    """Generates Snort/Suricata IDS rules based on target behaviour.

    Probes the target for open ports, HTTP response headers, and server software.
    Produces detection rules for: outbound DNS queries, HTTP header signatures,
    port connection attempts, and server software patterns. Educational tool
    for IDS/IPS rule authoring (Module 99).
    """

    scanner_name = "ids_rule_generator"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host, base_url = _normalize_target(input_value)

        # Resolve IP for rule generation
        loop = asyncio.get_event_loop()
        target_ip = await loop.run_in_executor(None, _resolve_ip, host)
        if not target_ip:
            target_ip = host  # Use literal if resolution fails

        rules: list[str] = []
        observations: list[str] = []
        sid_counter = _generate_sid()

        # 1. DNS query detection rule (always applicable for domains)
        if input_type == ScanInputType.DOMAIN:
            rules.append(_build_dns_rule(sid_counter, host))
            sid_counter += 1
            observations.append(f"Domain: {host} — DNS detection rule generated.")

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # 2. Probe common ports for banner/header intelligence
            async def probe_port(port: int) -> dict[str, Any] | None:
                url = f"{'https' if port == 443 else 'http'}://{host}:{port}/"
                try:
                    resp = await client.get(url)
                    return {
                        "port": port,
                        "status": resp.status_code,
                        "server": resp.headers.get("server", ""),
                        "x_powered_by": resp.headers.get("x-powered-by", ""),
                        "content_type": resp.headers.get("content-type", ""),
                    }
                except (httpx.RequestError, httpx.TimeoutException):
                    return None

            port_tasks = [probe_port(p) for p in _COMMON_PORTS[:6]]
            port_results = await asyncio.gather(*port_tasks, return_exceptions=True)

            for pr in port_results:
                if not isinstance(pr, dict):
                    continue
                port = pr["port"]
                server = pr.get("server", "")
                x_powered = pr.get("x_powered_by", "")

                # Port-based rule
                proto = "tcp"
                desc = f"Connection to {host}:{port}"
                rules.append(_build_port_rule(sid_counter, target_ip, port, proto, desc))
                sid_counter += 1
                observations.append(f"Port {port} open — connection detection rule generated.")

                # Server header rule
                if server:
                    rules.append(_build_http_header_rule(
                        sid_counter, target_ip, "Server", server,
                        f"HTTP response from {host} with Server header"
                    ))
                    sid_counter += 1
                    observations.append(f"Server: {server} — header signature rule generated.")

                if x_powered:
                    rules.append(_build_http_header_rule(
                        sid_counter, target_ip, "X-Powered-By", x_powered,
                        f"HTTP response from {host} with X-Powered-By header"
                    ))
                    sid_counter += 1
                    observations.append(f"X-Powered-By: {x_powered} — header rule generated.")

        return {
            "target": host,
            "resolved_ip": target_ip,
            "found": len(rules) > 0,
            "rule_count": len(rules),
            "observations": observations,
            "snort_suricata_rules": rules,
            "usage_instructions": (
                "Place these rules in /etc/snort/rules/local.rules or "
                "/etc/suricata/rules/local.rules and reload the IDS engine. "
                "Adjust $HOME_NET to match your monitored network range."
            ),
            "educational_note": (
                "Snort/Suricata rules define packet patterns that trigger alerts when matched. "
                "Rules generated here are based on observed server behaviour and "
                "provide a starting point — tune thresholds and SID ranges for production use."
            ),
        }
