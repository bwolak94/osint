"""AD & Infrastructure Tools API — CME, Impacket, BloodHound, Enum4linux, Certipy, Bettercap, Aircrack, Metasploit, OpenVAS, Burp."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.crackmapexec_runner import CrackMapExecRunner
from src.adapters.scanners.pentest.impacket_runner import ImpacketRunner, IMPACKET_TOOLS
from src.adapters.scanners.pentest.bloodhound_runner import BloodHoundRunner
from src.adapters.scanners.pentest.enum4linux_runner import Enum4linuxRunner
from src.adapters.scanners.pentest.certipy_runner import CertipyRunner
from src.adapters.scanners.pentest.bettercap_runner import BettercapRunner
from src.adapters.scanners.pentest.aircrack_runner import AircrackRunner
from src.adapters.scanners.pentest.metasploit_runner import MetasploitRunner
from src.adapters.scanners.pentest.openvas_runner import OpenVASRunner
from src.adapters.scanners.pentest.burp_runner import BurpRunner

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/ad-infra-tools",
    tags=["ad-infra-tools"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Shared output schemas
# ---------------------------------------------------------------------------

class FindingOut(BaseModel):
    tool: str
    title: str
    severity: str | None = None
    description: str | None = None
    cvss_v3: float | None = None
    cve: list[str] = []
    cwe: int | None = None
    host: str | None = None
    port: int | None = None
    url: str | None = None
    evidence: dict[str, Any] = {}


class ToolRunResult(BaseModel):
    tool: str
    exit_code: int
    duration_seconds: float
    findings: list[FindingOut]
    error: str | None = None
    findings_count: int = 0
    metadata: dict[str, Any] = {}


def _to_result(result: Any) -> ToolRunResult:
    findings = [
        FindingOut(
            tool=f.tool, title=f.title, severity=f.severity,
            description=f.description, cvss_v3=f.cvss_v3,
            cve=f.cve, cwe=f.cwe, host=f.host,
            port=f.port, url=f.url, evidence=f.evidence,
        )
        for f in result.findings
    ]
    return ToolRunResult(
        tool=result.tool,
        exit_code=result.exit_code,
        duration_seconds=result.duration_seconds,
        findings=findings,
        error=result.error,
        findings_count=len(findings),
        metadata=getattr(result, "metadata", {}) or {},
    )


# ---------------------------------------------------------------------------
# CrackMapExec
# ---------------------------------------------------------------------------

class CMERequest(BaseModel):
    target: str = Field(..., description="IP, CIDR, or hostname")
    protocol: str = Field("smb", description="Protocol: smb | ldap | winrm | mssql | ssh | rdp")
    action: str = Field("enum", description="Action: enum | shares | users | sessions | sam | lsa | exec")
    username: str | None = None
    password: str | None = None
    hash: str | None = Field(None, description="NTLM hash for pass-the-hash (LM:NT)")
    domain: str | None = None
    local_auth: bool = False
    command: str | None = Field(None, description="Command to execute (action=exec)")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/crackmapexec", response_model=ToolRunResult, summary="CrackMapExec SMB/AD enumeration")
async def run_cme(req: CMERequest) -> ToolRunResult:
    """Enumerate SMB shares, users, sessions. Test credentials. Pass-the-hash. Remote command exec."""
    opts = dict(req.options)
    for k in ("protocol", "action", "username", "password", "hash", "domain", "local_auth", "command"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await CrackMapExecRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Impacket
# ---------------------------------------------------------------------------

class ImpacketRequest(BaseModel):
    target: str = Field(..., description="Target hostname or IP")
    tool: str = Field("secretsdump", description=f"Tool: {', '.join(IMPACKET_TOOLS)}")
    domain: str | None = None
    username: str | None = None
    password: str | None = None
    hashes: str | None = Field(None, description="NTLM hashes LM:NT")
    dc_ip: str | None = Field(None, description="Domain controller IP")
    just_dc: bool = False
    request: bool = Field(False, description="Request TGS tickets (GetUserSPNs)")
    no_pass: bool = Field(False, description="No password for AS-REP (GetNPUsers)")
    extra_args: str | None = Field(None, description="Extra arguments string")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/impacket", response_model=ToolRunResult, summary="Impacket suite")
async def run_impacket(req: ImpacketRequest) -> ToolRunResult:
    """Run Impacket tools: secretsdump, GetUserSPNs, GetNPUsers, lookupsid, samrdump, rpcdump."""
    opts = dict(req.options)
    for k in ("tool", "domain", "username", "password", "hashes", "dc_ip", "just_dc", "request", "no_pass", "extra_args"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await ImpacketRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# BloodHound
# ---------------------------------------------------------------------------

class BloodHoundRequest(BaseModel):
    domain: str = Field(..., description="Active Directory domain name")
    dc_ip: str = Field(..., description="Domain controller IP address")
    username: str = Field(..., description="AD username")
    password: str = Field(..., description="AD password")
    collection: str = Field("All", description="Collection method: All | DCOnly | Default | Session | LoggedOn | Trusts | ACL | Container | RDP | DCOM | PSRemote")
    use_ldaps: bool = False
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/bloodhound", response_model=ToolRunResult, summary="BloodHound AD ingestor")
async def run_bloodhound(req: BloodHoundRequest) -> ToolRunResult:
    """Collect Active Directory data for BloodHound attack path analysis."""
    opts = dict(req.options)
    opts.update({"domain": req.domain, "dc_ip": req.dc_ip, "username": req.username,
                  "password": req.password, "collection": req.collection, "use_ldaps": req.use_ldaps})
    result = await BloodHoundRunner().run(req.domain, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Enum4linux
# ---------------------------------------------------------------------------

class Enum4linuxRequest(BaseModel):
    target: str = Field(..., description="Target Windows/Samba host IP or hostname")
    username: str | None = None
    password: str | None = None
    workgroup: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/enum4linux", response_model=ToolRunResult, summary="enum4linux-ng Windows/Samba enumeration")
async def run_enum4linux(req: Enum4linuxRequest) -> ToolRunResult:
    """Enumerate Windows/Samba hosts: users, shares, password policy, OS info via RPC/SMB."""
    opts = dict(req.options)
    for k in ("username", "password", "workgroup"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await Enum4linuxRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Certipy
# ---------------------------------------------------------------------------

class CertipyRequest(BaseModel):
    target: str = Field(..., description="Domain name or DC IP")
    action: str = Field("find", description="Action: find | auth | shadow | req")
    domain: str | None = None
    dc_ip: str | None = None
    username: str | None = None
    password: str | None = None
    account: str | None = Field(None, description="Target account for shadow attack")
    pfx: str | None = Field(None, description="PFX file path for auth action")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/certipy", response_model=ToolRunResult, summary="Certipy AD CS abuse scanner")
async def run_certipy(req: CertipyRequest) -> ToolRunResult:
    """Detect ESC1-ESC8 Active Directory Certificate Services vulnerabilities."""
    opts = dict(req.options)
    for k in ("action", "domain", "dc_ip", "username", "password", "account", "pfx"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await CertipyRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Bettercap
# ---------------------------------------------------------------------------

class BettercapRequest(BaseModel):
    target: str = Field(..., description="Target IP or subnet for ARP spoofing")
    interface: str = Field("eth0", description="Network interface")
    mode: str = Field("probe", description="Mode: probe | arp_spoof | dns_spoof | sniffer | full")
    duration: int = Field(30, ge=5, le=120, description="Capture duration in seconds")
    dns_spoof_address: str | None = Field(None, description="IP to redirect DNS queries to")
    dns_spoof_domains: str | None = Field(None, description="Comma-separated domains to spoof")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/bettercap", response_model=ToolRunResult, summary="Bettercap MitM framework")
async def run_bettercap(req: BettercapRequest) -> ToolRunResult:
    """Run Bettercap for ARP/DNS spoofing, network discovery, and credential capture. Requires root."""
    opts = dict(req.options)
    for k in ("interface", "mode", "duration", "dns_spoof_address", "dns_spoof_domains"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await BettercapRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Aircrack
# ---------------------------------------------------------------------------

class AircrackRequest(BaseModel):
    target: str = Field(..., description="Capture file path (crack/check_cap) or interface name (airodump)")
    action: str = Field("crack", description="Action: crack | airodump | check_cap")
    wordlist: str | None = Field(None, description="Path to wordlist for cracking")
    bssid: str | None = Field(None, description="Target AP BSSID")
    essid: str | None = Field(None, description="Target AP ESSID")
    channel: int | None = Field(None, description="Channel for airodump")
    duration: int = Field(30, ge=5, le=120, description="Capture duration (airodump mode)")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/aircrack", response_model=ToolRunResult, summary="Aircrack-ng WiFi security suite")
async def run_aircrack(req: AircrackRequest) -> ToolRunResult:
    """Crack WPA/WPA2 handshakes, scan for APs, or verify capture files contain valid handshakes."""
    opts = dict(req.options)
    for k in ("action", "wordlist", "bssid", "essid", "channel", "duration"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await AircrackRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Metasploit
# ---------------------------------------------------------------------------

class MetasploitRequest(BaseModel):
    target: str = Field("", description="Target IP/host (used as RHOSTS default)")
    rpc_url: str = Field("http://127.0.0.1:55553", description="msfrpcd URL")
    rpc_user: str = Field("msf", description="msfrpcd username")
    rpc_password: str = Field(..., description="msfrpcd password")
    action: str = Field("sessions", description="Action: sessions | search | info | run_module | kill_session")
    module: str | None = Field(None, description="Module path, e.g. auxiliary/scanner/smb/smb_ms17_010")
    module_options: dict[str, Any] = Field(default_factory=dict)
    query: str | None = Field(None, description="Search query (action=search)")
    session_id: str | None = Field(None, description="Session ID (kill_session)")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/metasploit", response_model=ToolRunResult, summary="Metasploit RPC integration")
async def run_metasploit(req: MetasploitRequest) -> ToolRunResult:
    """Connect to msfrpcd and manage sessions, search modules, run exploits, kill sessions."""
    opts = dict(req.options)
    for k in ("rpc_url", "rpc_user", "rpc_password", "action", "module", "module_options", "query", "session_id"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await MetasploitRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# OpenVAS
# ---------------------------------------------------------------------------

class OpenVASRequest(BaseModel):
    target: str = Field(..., description="Target IP/hostname to scan")
    action: str = Field("scan", description="Action: scan | list_tasks | get_results")
    gvm_host: str = Field("localhost", description="GVM/OpenVAS host")
    gvm_port: int = Field(9390, description="GVM port")
    username: str = Field("admin", description="GVM username")
    password: str = Field(..., description="GVM password")
    connection_type: str = Field("TLS", description="Connection: TLS | SSH | Unix")
    task_id: str | None = Field(None, description="Task ID for get_results action")
    scan_config_id: str | None = Field(None, description="Scan config UUID (default: Full and Fast)")
    max_wait: int = Field(600, ge=60, le=3600, description="Max seconds to wait for scan completion")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/openvas", response_model=ToolRunResult, summary="OpenVAS/GVM vulnerability scanner")
async def run_openvas(req: OpenVASRequest) -> ToolRunResult:
    """Run OpenVAS full vulnerability scan via GMP API. Creates target, task, polls to completion, returns findings."""
    opts = dict(req.options)
    for k in ("action", "gvm_host", "gvm_port", "username", "password", "connection_type", "task_id", "scan_config_id", "max_wait"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await OpenVASRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Burp Suite
# ---------------------------------------------------------------------------

class BurpRequest(BaseModel):
    target: str = Field("", description="Target URL for new scan")
    burp_url: str = Field("http://127.0.0.1:1337", description="Burp REST API URL")
    api_key: str | None = Field(None, description="Burp REST API key")
    action: str = Field("get_issues", description="Action: get_issues | scan | scan_status | list_scans")
    scan_id: str | None = Field(None, description="Scan ID for scan_status action")
    base_url: str | None = Field(None, description="Filter issues by base URL")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/burp", response_model=ToolRunResult, summary="Burp Suite REST API bridge")
async def run_burp(req: BurpRequest) -> ToolRunResult:
    """Connect to Burp Suite Professional REST API — retrieve issues, start scans, check status."""
    opts = dict(req.options)
    for k in ("burp_url", "api_key", "action", "scan_id", "base_url"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await BurpRunner().run(req.target, opts)
    return _to_result(result)
