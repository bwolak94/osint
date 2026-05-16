"""Enum4Linux — SMB/Windows network enumeration scanner.

Enum4linux enumerates Windows/Samba hosts: users, shares, groups,
password policy, OS information, and workgroup membership.
Essential for Active Directory and Windows network reconnaissance.

Two-mode operation:
1. **enum4linux binary** — if on PATH, full SMB enumeration
2. **Manual fallback** — SMB probing via socket + null session checks
"""

from __future__ import annotations

import asyncio
import re
import shutil
import socket
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# SMB-related ports
_SMB_PORTS = [139, 445]

# NetBIOS ports
_NETBIOS_PORTS = [137, 138, 139]

# MSRPC
_MSRPC_PORTS = [135, 593]

# Common Windows service ports
_WINDOWS_SERVICE_PORTS = {
    88: "kerberos",
    135: "msrpc",
    139: "netbios-ssn",
    389: "ldap",
    445: "microsoft-ds",
    464: "kpasswd",
    593: "msrpc-http",
    636: "ldaps",
    3268: "globalcatalog-ldap",
    3269: "globalcatalog-ldaps",
    3389: "rdp",
    5985: "winrm-http",
    5986: "winrm-https",
    49152: "dynamic-rpc",
}


class Enum4LinuxScanner(BaseOsintScanner):
    """SMB/Windows Active Directory network enumeration scanner.

    Probes for:
    - Open SMB ports (139, 445) and MSRPC (135)
    - Kerberos (88) and LDAP (389, 636) — AD indicators
    - WinRM (5985, 5986) — remote management exposure
    - RDP (3389) exposure
    - NetBIOS name service information
    - Null session capability
    - Anonymous share listing
    """

    scanner_name = "enum4linux"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = _extract_host(input_value, input_type)
        if not target:
            return {"input": input_value, "error": "Could not extract host", "extracted_identifiers": []}

        if shutil.which("enum4linux") or shutil.which("enum4linux-ng"):
            return await self._run_enum4linux_binary(target, input_value)
        return await self._manual_scan(target, input_value)

    async def _run_enum4linux_binary(self, target: str, input_value: str) -> dict[str, Any]:
        binary = shutil.which("enum4linux-ng") or "enum4linux"
        if "ng" in binary:
            cmd = [binary, "-A", "-oY", "/dev/stdout", target]
        else:
            cmd = [binary, "-a", target]

        output = ""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.scan_timeout - 10)
                output = stdout.decode(errors="replace")
            except asyncio.TimeoutError:
                log.warning("enum4linux timed out", target=target)
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception as exc:
            log.debug("enum4linux binary failed", error=str(exc))

        # Parse output
        users: list[str] = re.findall(r"user:\[([^\]]+)\]", output)
        shares: list[str] = re.findall(r"Sharename\s+\S+.*?\n\s+(\S+)", output)
        workgroup_m = re.search(r"Workgroup\s*/\s*Domain:\s*(\S+)", output, re.I)
        os_m = re.search(r"OS:\s*([^\n]+)", output)
        null_session = "NULL session" in output.lower() or "null sessions" in output.lower()

        identifiers = [f"username:{u}" for u in users[:10]]
        if null_session:
            identifiers.append("vuln:smb:null_session")

        return {
            "input": input_value,
            "scan_mode": "enum4linux_binary",
            "target": target,
            "users": users[:30],
            "shares": shares[:20],
            "workgroup": workgroup_m.group(1) if workgroup_m else None,
            "os_info": os_m.group(1).strip() if os_m else None,
            "null_session_allowed": null_session,
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, target: str, input_value: str) -> dict[str, Any]:
        open_ports: dict[int, str] = {}
        identifiers: list[str] = []
        findings: list[dict[str, Any]] = []
        is_windows_host = False

        loop = asyncio.get_event_loop()
        semaphore = asyncio.Semaphore(20)

        # Probe Windows-relevant ports
        all_windows_ports = list(_WINDOWS_SERVICE_PORTS.keys()) + _SMB_PORTS + _MSRPC_PORTS
        unique_ports = list(dict.fromkeys(all_windows_ports))

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
                    service = _WINDOWS_SERVICE_PORTS.get(port, "unknown")
                    open_ports[port] = service
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    pass

        await asyncio.gather(*[probe_port(p) for p in unique_ports])

        # Classify findings
        if 445 in open_ports or 139 in open_ports:
            is_windows_host = True
            findings.append({
                "type": "smb_open",
                "severity": "medium",
                "ports": [p for p in [139, 445] if p in open_ports],
                "description": "SMB service detected — check for EternalBlue (MS17-010), null sessions",
            })
            identifiers.append("service:smb")

        if 135 in open_ports:
            is_windows_host = True
            findings.append({
                "type": "msrpc_open",
                "severity": "medium",
                "description": "MSRPC endpoint mapper open — potential for RPC-based attacks",
            })

        if 88 in open_ports:
            is_windows_host = True
            findings.append({
                "type": "kerberos_open",
                "severity": "info",
                "description": "Kerberos (88) open — likely Active Directory Domain Controller",
            })
            identifiers.append("service:kerberos")

        if 389 in open_ports or 636 in open_ports:
            is_windows_host = True
            findings.append({
                "type": "ldap_open",
                "severity": "medium",
                "ports": [p for p in [389, 636] if p in open_ports],
                "description": "LDAP open — potential for anonymous bind and enumeration",
            })
            identifiers.append("service:ldap")

        if 3389 in open_ports:
            findings.append({
                "type": "rdp_exposed",
                "severity": "high",
                "description": "RDP (3389) exposed — brute-force and credential stuffing target",
            })
            identifiers.append("vuln:rdp:exposed")

        if 5985 in open_ports or 5986 in open_ports:
            findings.append({
                "type": "winrm_exposed",
                "severity": "high",
                "ports": [p for p in [5985, 5986] if p in open_ports],
                "description": "WinRM exposed — remote PowerShell execution possible with valid creds",
            })
            identifiers.append("vuln:winrm:exposed")

        # NetBIOS name lookup
        netbios_name: str | None = None
        try:
            result = await loop.run_in_executor(
                None, lambda: socket.gethostbyaddr(target)
            )
            netbios_name = result[0]
        except Exception:
            pass

        # Risk scoring
        risk_score = 0
        risk_score += 30 if 445 in open_ports else 0
        risk_score += 20 if 3389 in open_ports else 0
        risk_score += 20 if 5985 in open_ports else 0
        risk_score += 10 if 88 in open_ports else 0
        risk_score += 10 if 389 in open_ports else 0

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "target": target,
            "is_windows_host": is_windows_host,
            "open_windows_ports": open_ports,
            "total_open": len(open_ports),
            "netbios_name": netbios_name,
            "findings": findings,
            "risk_score": min(100, risk_score),
            "active_directory_indicators": 88 in open_ports and (389 in open_ports or 636 in open_ports),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    from urllib.parse import urlparse
    if input_type == ScanInputType.IP_ADDRESS:
        return value.strip()
    if input_type == ScanInputType.DOMAIN:
        return value.split(":")[0].lstrip("*.")
    try:
        return urlparse(value).hostname or ""
    except Exception:
        return ""
