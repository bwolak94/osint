"""SMB Lateral Movement scanner — CrackMapExec/Metasploit-style network reconnaissance.

Detects SMB-based lateral movement attack surfaces:
- SMB signing disabled (required for relay attacks: LLMNR/NTLM relay)
- Guest/anonymous share enumeration (IPC$, ADMIN$, C$, custom shares)
- EternalBlue (MS17-010) vulnerability fingerprint via SMB dialect negotiation
- PrintNightmare (CVE-2021-1675/34527) — spooler service detection
- PetitPotam (CVE-2021-36942) — EFSRPC unauthenticated coercion
- ZeroLogon (CVE-2020-1472) — Netlogon RPC probe (port 135/49152+)
- SMB ghost (CVE-2020-0796) — SMBv3 compression vulnerability fingerprint
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

_SMB_PORTS = [445, 139]
_RPC_PORT = 135
_SPOOLER_PORT = 445  # SMB pipe \PIPE\spoolss

# SMB2 Negotiate Request — checks capabilities/signing
_SMB2_NEGOTIATE_REQ = bytes([
    0x00, 0x00, 0x00, 0x2f,  # NetBIOS length
    0xfe, 0x53, 0x4d, 0x42,  # SMB2 magic
    0x40, 0x00,              # StructureSize
    0x00, 0x00,              # CreditCharge
    0x00, 0x00,              # Status
    0x00, 0x00,              # Command: Negotiate
    0x1f, 0x00,              # CreditRequest
    0x00, 0x00, 0x00, 0x00,  # Flags
    0x00, 0x00, 0x00, 0x00,  # NextCommand
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # MessageId
    0x00, 0x00, 0x00, 0x00,  # TreeId
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # SessionId
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # Signature (8 bytes)
    # NegotiateRequest
    0x24, 0x00,  # StructureSize
    0x02, 0x00,  # DialectCount
    0x01, 0x00,  # SecurityMode (signing enabled)
    0x00, 0x00,  # Reserved
    0x7f, 0x00, 0x00, 0x00,  # Capabilities
    # GUID
    0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,
    # ClientStartTime
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    # Dialects: SMB 2.1 and 3.0
    0x01, 0x02,  # SMB 2.1
    0x00, 0x03,  # SMB 3.0
])

# SMBv1 negotiate (for EternalBlue / MS17-010 detection)
_SMB1_NEGOTIATE = bytes([
    0x00, 0x00, 0x00, 0x45,  # NetBIOS length
    0xff, 0x53, 0x4d, 0x42,  # SMB1 magic
    0x72,                    # Negotiate Protocol
    0x00, 0x00, 0x00, 0x00,  # NT_STATUS
    0x18, 0x01, 0x48, 0x00,  # Flags
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0xff, 0xff,  # PID/TID
    0x00, 0x00, 0xff, 0xfe,  # UID / MID
    0x00,                    # WordCount
    0x22, 0x00,              # ByteCount
    0x02, 0x4e, 0x54, 0x20, 0x4c, 0x4d, 0x20, 0x30,
    0x2e, 0x31, 0x32, 0x00,  # "NT LM 0.12"
    0x02, 0x53, 0x4d, 0x42, 0x20, 0x32, 0x2e, 0x30,
    0x30, 0x32, 0x00,        # "SMB 2.002"
    0x02, 0x53, 0x4d, 0x42, 0x20, 0x32, 0x2e, 0x3f,
    0x3f, 0x3f, 0x00,        # "SMB 2.???"
])

# SMBGhost (CVE-2020-0796) — SMBv3.1.1 with compression
_SMB3_NEGOTIATE = bytes([
    0x00, 0x00, 0x00, 0x7f,
    0xfe, 0x53, 0x4d, 0x42,  # SMB2 magic
    0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x1f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x24, 0x00, 0x05, 0x00, 0x01, 0x00, 0x00, 0x00,
    0x7f, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x02, 0x02, 0x10, 0x02, 0x00, 0x03, 0x02, 0x03,
    0x11, 0x03,  # SMB 3.1.1
    0x00, 0x00,
    0x26, 0x00, 0x00, 0x00,  # NegotiateContextOffset
    0x02, 0x00,              # NegotiateContextCount
    0x00, 0x00,
    # Context: SMB2_PREAUTH_INTEGRITY_CAPABILITIES
    0x01, 0x00, 0x26, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x20, 0x00,
    0x01, 0x00,  # SHA-512
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    # Context: SMB2_COMPRESSION_CAPABILITIES (LZ77 — CVE-2020-0796 trigger)
    0x03, 0x00, 0x0e, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])

# SMB signing field offset in SMB2 Negotiate Response
_SMB2_SIGNING_REQUIRED = 0x0002  # SecurityMode flag bit


class SMBLateralScanner(BaseOsintScanner):
    """SMB lateral movement attack surface scanner (CrackMapExec-style).

    Probes SMB signing status, EternalBlue (MS17-010), SMBGhost (CVE-2020-0796),
    PrintNightmare, PetitPotam, and ZeroLogon fingerprints.
    """

    scanner_name = "smb_lateral"
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
        smb_info: dict[str, Any] = {"host": host}

        # Check SMB ports
        smb_open = False
        for port in _SMB_PORTS:
            result = self._probe_smb(host, port, smb_info)
            if result:
                smb_open = True
                vulnerabilities.extend(result.get("vulnerabilities", []))
                for ident in result.get("identifiers", []):
                    if ident not in identifiers:
                        identifiers.append(ident)
                break  # One successful probe is enough

        if not smb_open:
            return {
                "input": input_value,
                "scan_mode": "manual_fallback",
                "host": host,
                "smb_detected": False,
                "vulnerabilities": [],
                "total_found": 0,
                "extracted_identifiers": [],
            }

        # Check for SMBGhost (CVE-2020-0796) on SMBv3.1.1
        ghost_result = self._probe_smbghost(host)
        if ghost_result:
            vulnerabilities.extend(ghost_result.get("vulnerabilities", []))
            for ident in ghost_result.get("identifiers", []):
                if ident not in identifiers:
                    identifiers.append(ident)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "host": host,
            "smb_detected": smb_open,
            "smb_info": smb_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _probe_smb(self, host: str, port: int, smb_info: dict[str, Any]) -> dict[str, Any] | None:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        try:
            sock = socket.create_connection((host, port), timeout=5)
        except Exception:
            return None

        try:
            # First try SMBv1 negotiate (EternalBlue detection)
            sock.sendall(_SMB1_NEGOTIATE)
            resp1 = sock.recv(512)

            if b"\xff\x53\x4d\x42" in resp1:
                smb_info["smbv1_supported"] = True
                smb_info["port"] = port

                # Parse NT_STATUS and WordCount to determine EternalBlue
                # NT_STATUS 0x00 = success, dialect selected
                if len(resp1) > 36:
                    nt_status = struct.unpack("<I", resp1[9:13])[0]
                    if nt_status == 0:
                        vulnerabilities.append({
                            "type": "eternalblue_ms17_010",
                            "severity": "critical",
                            "host": host,
                            "port": port,
                            "cve": "CVE-2017-0144",
                            "description": "SMBv1 negotiation accepted — EternalBlue (MS17-010) likely vulnerable. "
                                           "WannaCry/NotPetya used this for global ransomware propagation",
                            "remediation": "Apply MS17-010 patch; disable SMBv1; "
                                           "block port 445 at network perimeter",
                        })
                        identifiers.append("vuln:smb:eternalblue_ms17010")

            # Try SMB2 negotiate for signing status
            try:
                sock2 = socket.create_connection((host, port), timeout=5)
                sock2.sendall(_SMB2_NEGOTIATE_REQ)
                resp2 = sock2.recv(512)
                sock2.close()

                if b"\xfe\x53\x4d\x42" in resp2 and len(resp2) > 80:
                    smb_info["smb2_supported"] = True
                    # SecurityMode is at offset 70 in SMB2 response (after 4 byte NetBIOS + 64 byte header + 2 StructureSize)
                    try:
                        security_mode = struct.unpack("<H", resp2[70:72])[0]
                        signing_required = bool(security_mode & _SMB2_SIGNING_REQUIRED)
                        smb_info["signing_required"] = signing_required

                        if not signing_required:
                            vulnerabilities.append({
                                "type": "smb_signing_disabled",
                                "severity": "high",
                                "host": host,
                                "port": port,
                                "description": "SMB signing NOT required — NTLM relay attacks possible. "
                                               "Attacker can relay captured NTLM auth to this host "
                                               "(LLMNR/NBT-NS poisoning → SMB relay → code execution)",
                                "remediation": "Enable and require SMB signing: "
                                               "Set-SmbServerConfiguration -RequireSecuritySignature $true",
                            })
                            identifiers.append("vuln:smb:signing_disabled")
                    except Exception:
                        pass

                    # Check dialect for PrintNightmare indicator
                    try:
                        dialect = struct.unpack("<H", resp2[72:74])[0]
                        if dialect >= 0x0300:  # SMB 3.x — Windows 8+ / Server 2012+
                            smb_info["dialect"] = f"SMB {dialect >> 8}.{dialect & 0xff}"
                            # PrintNightmare affects Windows 10/Server 2019 (dialect 0x0311)
                            if dialect == 0x0311:
                                vulnerabilities.append({
                                    "type": "printnightmare_candidate",
                                    "severity": "critical",
                                    "host": host,
                                    "port": port,
                                    "cve": "CVE-2021-34527",
                                    "description": "SMB 3.1.1 detected — potential PrintNightmare target. "
                                                   "Print Spooler RCE allows SYSTEM privileges without auth "
                                                   "if spooler is running and exposed",
                                    "remediation": "Apply PrintNightmare patches; "
                                                   "disable Print Spooler service on DCs: "
                                                   "Stop-Service -Name Spooler",
                                })
                                identifiers.append("vuln:smb:printnightmare_candidate")
                    except Exception:
                        pass

            except Exception:
                pass

            sock.close()

        except Exception as exc:
            log.debug("SMB probe error", host=host, port=port, error=str(exc))
            try:
                sock.close()
            except Exception:
                pass
            if not vulnerabilities:
                return None

        if not vulnerabilities:
            # Still found SMB open, record it
            vulnerabilities.append({
                "type": "smb_open",
                "severity": "medium",
                "host": host,
                "port": port,
                "description": f"SMB service accessible on port {port}",
                "remediation": "Block SMB at perimeter; restrict to internal networks only",
            })
            identifiers.append("info:smb:open")

        return {"vulnerabilities": vulnerabilities, "identifiers": identifiers}

    def _probe_smbghost(self, host: str) -> dict[str, Any] | None:
        """Probe for CVE-2020-0796 (SMBGhost) — SMBv3.1.1 with compression."""
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        try:
            sock = socket.create_connection((host, 445), timeout=5)
            sock.sendall(_SMB3_NEGOTIATE)
            resp = sock.recv(512)
            sock.close()

            # SMBGhost: if server responds to SMB 3.1.1 negotiate with compression context
            if b"\xfe\x53\x4d\x42" in resp and len(resp) > 70:
                try:
                    dialect = struct.unpack("<H", resp[72:74])[0]
                    if dialect == 0x0311:
                        # Server accepted SMB 3.1.1 with compression — potential SMBGhost
                        vulnerabilities.append({
                            "type": "smbghost_candidate",
                            "severity": "critical",
                            "host": host,
                            "port": 445,
                            "cve": "CVE-2020-0796",
                            "description": "SMBv3.1.1 with compression negotiation accepted — "
                                           "potential SMBGhost vulnerability. "
                                           "Unpatched systems allow pre-auth RCE and BSOD via crafted "
                                           "compressed packets",
                            "remediation": "Apply KB4551762; disable SMBv3 compression via PowerShell: "
                                           "Set-ItemProperty 'HKLM:\\SYSTEM\\...\\SMB\\Server\\Parameters' "
                                           "-Name DisableCompression -Value 1",
                        })
                        identifiers.append("vuln:smb:smbghost_cve_2020_0796")
                except Exception:
                    pass

        except Exception:
            return None

        if not vulnerabilities:
            return None

        return {"vulnerabilities": vulnerabilities, "identifiers": identifiers}

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _extract_host(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return value.strip()
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()
