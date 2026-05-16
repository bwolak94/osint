"""Masscan — fast TCP port scanner (complement to nmap/naabu).

Masscan is the fastest Internet port scanner. At 10 Gbps it can scan the
entire Internet in ~6 minutes. Used here for targeted fast port discovery.

Two-mode operation:
1. **masscan binary** — if on PATH, invoked for fast TCP port scanning
2. **Manual fallback** — asyncio-based TCP connect scan (top ports)
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
from urllib.parse import urlparse

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Top 100 ports — covers the vast majority of real-world services
_TOP_PORTS: list[int] = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139,
    143, 194, 443, 445, 465, 587, 993, 995, 1080,
    1194, 1433, 1521, 1723, 2049, 2082, 2083, 2086, 2087,
    2095, 2096, 3000, 3306, 3389, 3690, 4000, 4443, 4444,
    4848, 5000, 5432, 5601, 5672, 5900, 5984, 6379, 6443,
    6881, 7000, 7001, 7443, 7474, 8000, 8008, 8080, 8081,
    8082, 8083, 8085, 8086, 8087, 8088, 8089, 8090, 8091,
    8092, 8093, 8094, 8095, 8096, 8097, 8098, 8099, 8100,
    8180, 8200, 8443, 8444, 8500, 8787, 8888, 8983, 9000,
    9001, 9042, 9090, 9092, 9200, 9300, 9418, 9443, 9999,
    10000, 11211, 15672, 27017, 27018, 28017, 50070, 50075,
]

# Service banners by port number
_PORT_SERVICES: dict[int, str] = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 143: "imap", 194: "irc",
    443: "https", 445: "smb", 465: "smtps", 587: "submission",
    993: "imaps", 995: "pop3s", 1080: "socks5", 1433: "mssql",
    1521: "oracle", 3000: "dev-server", 3306: "mysql", 3389: "rdp",
    5432: "postgresql", 5672: "amqp", 5900: "vnc", 5984: "couchdb",
    6379: "redis", 7474: "neo4j", 8080: "http-proxy", 8443: "https-alt",
    9200: "elasticsearch", 9300: "elasticsearch-transport",
    11211: "memcached", 15672: "rabbitmq-mgmt", 27017: "mongodb",
    50070: "hadoop-namenode",
}

# Ports that indicate critical exposures
_CRITICAL_PORTS: set[int] = {21, 23, 445, 1433, 3306, 3389, 5432, 5900, 6379, 11211, 27017}
_HIGH_PORTS: set[int] = {22, 25, 110, 143, 1521, 4444, 5672, 9200, 9300, 50070}


class MasscanScanner(BaseOsintScanner):
    """Fast TCP port scanner using masscan or asyncio connect probes.

    Discovers open TCP ports, identifies running services, and flags
    critical/dangerous service exposures. Complements nmap with speed.
    """

    scanner_name = "masscan"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = _extract_host(input_value, input_type)
        if not target:
            return {"input": input_value, "error": "Could not extract host", "extracted_identifiers": []}

        if shutil.which("masscan"):
            return await self._run_masscan_binary(target, input_value)
        return await self._manual_scan(target, input_value)

    async def _run_masscan_binary(self, target: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"masscan_{run_id}.json")
        ports_str = ",".join(str(p) for p in _TOP_PORTS)
        cmd = [
            "masscan",
            target,
            f"-p{ports_str}",
            "--rate", "1000",
            "--output-format", "json",
            "--output-filename", out_file,
            "--wait", "3",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("masscan timed out", target=target)
            try:
                proc.kill()
            except Exception:
                pass

        open_ports: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    content = fh.read().strip()
                    # Masscan JSON is not valid JSON array — wrap it
                    if content and not content.startswith("["):
                        content = f"[{content.rstrip(',')}]"
                    data = json.loads(content)
                for entry in data if isinstance(data, list) else []:
                    for port_entry in entry.get("ports", []):
                        port = port_entry.get("port", 0)
                        open_ports.append({
                            "port": port,
                            "protocol": port_entry.get("proto", "tcp"),
                            "service": _PORT_SERVICES.get(port, "unknown"),
                            "state": "open",
                        })
            except Exception as exc:
                log.warning("Failed to parse masscan output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        return _build_result(input_value, target, open_ports, "masscan_binary")

    async def _manual_scan(self, target: str, input_value: str) -> dict[str, Any]:
        open_ports: list[dict[str, Any]] = []
        semaphore = asyncio.Semaphore(50)

        async def probe_port(port: int) -> None:
            async with semaphore:
                try:
                    conn = asyncio.open_connection(target, port)
                    reader, writer = await asyncio.wait_for(conn, timeout=2.0)
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    open_ports.append({
                        "port": port,
                        "protocol": "tcp",
                        "service": _PORT_SERVICES.get(port, "unknown"),
                        "state": "open",
                    })
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    pass
                except Exception:
                    pass

        tasks = [probe_port(p) for p in _TOP_PORTS]
        await asyncio.gather(*tasks)

        return _build_result(input_value, target, open_ports, "manual_fallback")

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _build_result(input_value: str, target: str, open_ports: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    open_ports.sort(key=lambda x: x["port"])
    port_numbers = [p["port"] for p in open_ports]

    critical_exposed = [p for p in open_ports if p["port"] in _CRITICAL_PORTS]
    high_exposed = [p for p in open_ports if p["port"] in _HIGH_PORTS]

    identifiers = [f"port:{p['port']}/{p['service']}" for p in open_ports]
    for p in critical_exposed:
        identifiers.insert(0, f"vuln:exposed_service:{p['service']}:{p['port']}")

    return {
        "input": input_value,
        "scan_mode": mode,
        "target": target,
        "open_ports": open_ports,
        "total_open": len(open_ports),
        "port_numbers": port_numbers,
        "services": {p["port"]: p["service"] for p in open_ports},
        "critical_exposures": critical_exposed,
        "high_risk_ports": high_exposed,
        "risk_summary": {
            "critical": len(critical_exposed),
            "high": len(high_exposed),
            "total_open": len(open_ports),
        },
        "extracted_identifiers": identifiers,
    }


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.IP_ADDRESS:
        return value.strip()
    if input_type == ScanInputType.DOMAIN:
        return value.split(":")[0].lstrip("*.")
    try:
        return urlparse(value).hostname or ""
    except Exception:
        return ""
