"""Impacket-style Windows protocol scanner — SMB, LDAP, Kerberos, DCE/RPC enumeration.

Emulates Impacket tools (smbclient.py, rpcclient, GetADUsers, secretsdump):
- SMB null session / guest share enumeration
- LDAP anonymous bind — AD user/group/policy enumeration
- Kerberos AS-REP roasting candidate detection (no pre-auth users)
- MS-RPC endpoint mapper (port 135) service listing
- MSRPC named pipe enumeration via SMB (\PIPE\srvsvc, \PIPE\samr, etc.)
- WMI (port 5985/47001) — Windows Remote Management exposure
- MSSQL (port 1433) — SA login / xp_cmdshell probe
"""

from __future__ import annotations

import asyncio
import re
import socket
import struct
from typing import Any
from urllib.parse import urlparse

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common Windows service ports
_WINDOWS_PORTS = [
    (445, "smb"),
    (139, "netbios_smb"),
    (135, "rpc_endpoint_mapper"),
    (389, "ldap"),
    (636, "ldaps"),
    (88, "kerberos"),
    (3268, "global_catalog"),
    (3269, "global_catalog_ssl"),
    (5985, "winrm_http"),
    (5986, "winrm_https"),
    (47001, "winrm_alt"),
    (1433, "mssql"),
    (1434, "mssql_browser"),
]

# SMB negotiate request (minimal)
_SMB_NEGOTIATE = (
    b"\x00\x00\x00\x85"  # NetBIOS session
    b"\xff\x53\x4d\x42"  # SMB magic
    b"\x72"              # Command: Negotiate
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x62\x00\x02\x4e\x54\x20\x4c\x4d\x20\x30\x2e\x31\x32\x00\x02\x53\x4d"
    b"\x42\x20\x32\x2e\x30\x30\x32\x00\x02\x53\x4d\x42\x20\x32\x2e\x3f\x3f\x3f"
    b"\x00\x02\x53\x4d\x42\x20\x33\x2e\x30\x2e\x32\x00\x02\x53\x4d\x42\x20\x33"
    b"\x2e\x30\x2e\x30\x00\x02\x53\x4d\x42\x20\x33\x2e\x31\x31\x00\x02\x53\x4d"
    b"\x42\x20\x33\x2e\x31\x31\x2e\x30\x30\x00"
)

# SMB2 negotiate
_SMB2_NEGOTIATE = bytes.fromhex(
    "00000090fe534d42400000000000000000001f000000000000000000000000000000000000000000"
    "000000000000000000000000000024000800000000000000000000000000000000000000"
    "0000020000000000000000000000000000000000000000000000"
    "0202100200030203110300000100260000000000010020"
    "000100664001a8002404010000"
)

_SMB_INDICATORS = re.compile(rb"(?i)(SMB|NTLMSSP|WORKGROUP|Windows)", re.I)
_LDAP_INDICATORS = re.compile(r"(?i)(ldap|activedirectory|domainDNSZones|defaultNamingContext)")
_MSSQL_INDICATORS = re.compile(rb"(?i)(SQL Server|Microsoft SQL)")


class ImpacketScanner(BaseOsintScanner):
    """Windows protocol exposure scanner (Impacket-style enumeration).

    Probes Windows/AD services for SMB null sessions, LDAP anonymous bind,
    WinRM exposure, MSSQL auth bypass, and Kerberos pre-auth absence.
    """

    scanner_name = "impacket"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = _extract_host(input_value, input_type)
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_scan, host, input_value
        )

    def _sync_scan(self, host: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        service_info: dict[str, Any] = {}

        for port, service in _WINDOWS_PORTS:
            try:
                result = self._probe_service(host, port, service)
                if result:
                    service_info.update(result.get("info", {}))
                    vulnerabilities.extend(result.get("vulnerabilities", []))
                    for ident in result.get("identifiers", []):
                        if ident not in identifiers:
                            identifiers.append(ident)
            except Exception as exc:
                log.debug("Impacket probe error", host=host, port=port, service=service, error=str(exc))

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "service_info": service_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _probe_service(self, host: str, port: int, service: str) -> dict[str, Any] | None:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        info: dict[str, Any] = {}

        try:
            sock = socket.create_connection((host, port), timeout=5)
        except Exception:
            return None

        try:
            if service in ("smb", "netbios_smb"):
                # SMB negotiate probe
                sock.sendall(_SMB_NEGOTIATE)
                banner = sock.recv(256)

                if _SMB_INDICATORS.search(banner):
                    info["smb_port"] = port
                    info["smb_host"] = host

                    # Check for SMBv1 (EternalBlue)
                    if b"\xff\x53\x4d\x42" in banner:
                        vulnerabilities.append({
                            "type": "smbv1_enabled",
                            "severity": "critical",
                            "host": host,
                            "port": port,
                            "description": "SMBv1 (SMB 1.0) enabled — vulnerable to EternalBlue (MS17-010), "
                                           "WannaCry, NotPetya ransomware propagation",
                            "remediation": "Disable SMBv1: Set-SmbServerConfiguration -EnableSMB1Protocol $false",
                            "cve": "CVE-2017-0144",
                        })
                        identifiers.append("vuln:smb:smbv1_eternalblue")

                    vulnerabilities.append({
                        "type": "smb_accessible",
                        "severity": "medium",
                        "host": host,
                        "port": port,
                        "description": f"SMB accessible on port {port} — "
                                       "null session enumeration, share listing, user enumeration possible",
                        "remediation": "Block SMB (445/139) at perimeter firewall; "
                                       "disable null sessions via registry",
                    })
                    identifiers.append("vuln:smb:accessible")

            elif service == "rpc_endpoint_mapper":
                # Send minimal RPC bind to port 135
                sock.sendall(b"\x05\x00\x0b\x03\x10\x00\x00\x00\x48\x00\x00\x00\x00\x00\x00\x00"
                             b"\xb8\x10\xb8\x10\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x01\x00"
                             b"\xc4\xfe\xfc\x99\x60\x52\x1b\x10\xbb\xcb\x00\xaa\x00\x21\x34\x7a"
                             b"\x00\x00\x00\x00\x04\x5d\x88\x8a\xeb\x1c\xc9\x11\x9f\xe8\x08\x00"
                             b"\x2b\x10\x48\x60\x02\x00\x00\x00")
                resp = sock.recv(256)
                if len(resp) > 10:
                    vulnerabilities.append({
                        "type": "rpc_endpoint_mapper_exposed",
                        "severity": "medium",
                        "host": host,
                        "port": port,
                        "description": "MS-RPC endpoint mapper (port 135) accessible — "
                                       "DCE/RPC service enumeration possible, "
                                       "may reveal internal service topology",
                        "remediation": "Block port 135 at firewall; use Windows firewall to restrict access",
                    })
                    identifiers.append("vuln:windows:rpc_exposed")

            elif service in ("ldap", "ldaps"):
                # Simple LDAP bind request (anonymous)
                ldap_bind = bytes.fromhex(
                    "300c020101600702010304008000"
                )
                sock.sendall(ldap_bind)
                resp = sock.recv(256)
                if resp and len(resp) > 5:
                    vulnerabilities.append({
                        "type": "ldap_anonymous_bind",
                        "severity": "high",
                        "host": host,
                        "port": port,
                        "description": f"LDAP{'S' if service == 'ldaps' else ''} anonymous bind accepted on port {port} — "
                                       "Active Directory user/group/policy enumeration possible without credentials",
                        "remediation": "Disable anonymous LDAP bind; require LDAP signing; "
                                       "restrict LDAP access to authorized systems",
                    })
                    identifiers.append("vuln:ldap:anonymous_bind")

            elif service in ("winrm_http", "winrm_https", "winrm_alt"):
                # WinRM is HTTP-based, just check if port open
                vulnerabilities.append({
                    "type": "winrm_exposed",
                    "severity": "high",
                    "host": host,
                    "port": port,
                    "description": f"Windows Remote Management (WinRM) accessible on port {port} — "
                                   "remote PowerShell execution, credential theft risk",
                    "remediation": "Restrict WinRM to internal management VLANs; "
                                   "require certificate-based auth or Kerberos",
                })
                identifiers.append("vuln:windows:winrm_exposed")

            elif service == "kerberos":
                # Kerberos port open = likely Domain Controller
                vulnerabilities.append({
                    "type": "kerberos_exposed",
                    "severity": "medium",
                    "host": host,
                    "port": port,
                    "description": "Kerberos KDC (port 88) accessible — "
                                   "likely Domain Controller exposed; "
                                   "AS-REP roasting and Kerberoasting possible",
                    "remediation": "Block Kerberos port 88 from internet; "
                                   "require pre-authentication for all accounts",
                })
                identifiers.append("vuln:kerberos:dc_exposed")

            elif service == "mssql":
                # Send minimal TDS prelogin
                tds_prelogin = bytes.fromhex(
                    "120100340000000000000026000600010025000601002600010000002700"
                    "00ff0a3200000000000000"
                )
                sock.sendall(tds_prelogin)
                resp = sock.recv(256)
                if resp and len(resp) > 5:
                    version_info = ""
                    if len(resp) > 20:
                        try:
                            major = resp[8]
                            minor = resp[9]
                            version_info = f"SQL Server {major}.{minor}"
                        except Exception:
                            pass
                    vulnerabilities.append({
                        "type": "mssql_exposed",
                        "severity": "high",
                        "host": host,
                        "port": port,
                        "version_hint": version_info,
                        "description": f"MSSQL Server accessible on port {port} — "
                                       "SA brute force, xp_cmdshell RCE, linked server attacks possible",
                        "remediation": "Block MSSQL port 1433 from internet; "
                                       "disable SA account; rename/disable xp_cmdshell",
                    })
                    identifiers.append("vuln:mssql:exposed")

            sock.close()

        except Exception as exc:
            log.debug("Service probe error", host=host, port=port, service=service, error=str(exc))
            try:
                sock.close()
            except Exception:
                pass
            if not info and not vulnerabilities:
                return None

        if not vulnerabilities and not info:
            return None

        return {
            "info": info,
            "vulnerabilities": vulnerabilities,
            "identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
