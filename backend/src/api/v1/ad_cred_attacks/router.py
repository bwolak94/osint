"""AD Credential Attacks — Kerberoast, AS-REP Roast, Password Spray, Hashcat, Responder.

Improvement 4: Exposes AD-focused credential attack runners that previously had
no dedicated interactive API surface (redteam router uses them internally but
doesn't provide direct per-tool control with structured options).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.kerberoast_runner import KerberoastRunner
from src.adapters.scanners.pentest.asreproast_runner import AsRepRoastRunner
from src.adapters.scanners.pentest.spray_runner import SprayRunner
from src.adapters.scanners.pentest.hashcat_runner import HashcatRunner
from src.adapters.scanners.pentest.responder_runner import ResponderRunner
from src.adapters.scanners.pentest.mitre_attack import get_mitre_techniques

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/ad-cred-attacks",
    tags=["ad-cred-attacks"],
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
    mitre_techniques: list[str] = []


class ToolRunResult(BaseModel):
    tool: str
    exit_code: int
    duration_seconds: float
    findings: list[FindingOut]
    error: str | None = None
    findings_count: int = 0
    metadata: dict[str, Any] = {}


def _to_result(result: Any, tool_name: str = "") -> ToolRunResult:
    seen: set[str] = set()
    findings: list[FindingOut] = []
    for f in (result.findings or []):
        key = f"{f.title}|{f.host or ''}|{f.port or ''}"
        if key in seen:
            continue
        seen.add(key)
        mitre = get_mitre_techniques(f.title, f.description, f.tool)
        findings.append(FindingOut(
            tool=f.tool,
            title=f.title,
            severity=f.severity,
            description=f.description,
            cvss_v3=f.cvss_v3,
            cve=f.cve,
            cwe=f.cwe,
            host=f.host,
            port=f.port,
            url=f.url,
            evidence=f.evidence,
            mitre_techniques=mitre,
        ))
    name = getattr(result, "tool", tool_name) or tool_name
    return ToolRunResult(
        tool=name,
        exit_code=result.exit_code,
        duration_seconds=result.duration_seconds,
        findings=findings,
        error=result.error,
        findings_count=len(findings),
        metadata=getattr(result, "metadata", {}) or {},
    )


# ---------------------------------------------------------------------------
# Kerberoast
# ---------------------------------------------------------------------------

class KerberoastRequest(BaseModel):
    target: str = Field(..., description="Domain Controller IP or hostname")
    domain: str = Field(..., description="Active Directory domain (e.g. corp.local)")
    username: str = Field(..., description="Domain username for authentication")
    password: str | None = Field(None, description="Password (use hashes if omitted)")
    hashes: str | None = Field(None, description="NTLM hashes LM:NT for pass-the-hash")
    dc_ip: str | None = Field(None, description="Domain Controller IP override")
    request_tgs: bool = Field(True, description="Request and output TGS hashes for offline cracking")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/kerberoast", response_model=ToolRunResult, summary="Kerberoasting — enumerate and request SPN tickets")
async def run_kerberoast(req: KerberoastRequest) -> ToolRunResult:
    """Enumerate service accounts with SPNs and request TGS tickets for offline cracking. MITRE T1558.003."""
    opts = dict(req.options)
    opts.update({
        "domain": req.domain,
        "username": req.username,
        "request": req.request_tgs,
    })
    if req.password:
        opts["password"] = req.password
    if req.hashes:
        opts["hashes"] = req.hashes
    if req.dc_ip:
        opts["dc_ip"] = req.dc_ip
    result = await KerberoastRunner().run(req.target, opts)
    return _to_result(result, "kerberoast")


# ---------------------------------------------------------------------------
# AS-REP Roast
# ---------------------------------------------------------------------------

class ASREPRoastRequest(BaseModel):
    target: str = Field(..., description="Domain Controller IP or hostname")
    domain: str = Field(..., description="Active Directory domain")
    userfile: str | None = Field(None, description="Path to username list file on server")
    username: str | None = Field(None, description="Single username to test")
    dc_ip: str | None = Field(None, description="Domain Controller IP override")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/asreproast", response_model=ToolRunResult, summary="AS-REP Roasting — accounts without pre-auth")
async def run_asreproast(req: ASREPRoastRequest) -> ToolRunResult:
    """Find accounts with Kerberos pre-authentication disabled and capture AS-REP hashes. MITRE T1558.004."""
    opts = dict(req.options)
    opts["domain"] = req.domain
    if req.userfile:
        opts["userfile"] = req.userfile
    if req.username:
        opts["username"] = req.username
    if req.dc_ip:
        opts["dc_ip"] = req.dc_ip
    result = await AsRepRoastRunner().run(req.target, opts)
    return _to_result(result, "asreproast")


# ---------------------------------------------------------------------------
# Password Spray
# ---------------------------------------------------------------------------

class SprayRequest(BaseModel):
    target: str = Field(..., description="Target IP, CIDR, or hostname")
    password: str = Field(..., description="Password to spray")
    domain: str | None = Field(None, description="Active Directory domain")
    userfile: str | None = Field(None, description="Path to username file on server")
    protocol: str = Field("smb", description="Protocol: smb | ldap | winrm | ssh | rdp")
    delay: float = Field(1.0, ge=0.5, le=60.0, description="Delay between attempts in seconds (lockout avoidance)")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/spray", response_model=ToolRunResult, summary="Low-and-slow password spray")
async def run_spray(req: SprayRequest) -> ToolRunResult:
    """Spray a single password across multiple accounts. Lockout-aware with configurable delay. MITRE T1110.003."""
    opts = dict(req.options)
    opts.update({
        "password": req.password,
        "protocol": req.protocol,
        "delay": req.delay,
    })
    if req.domain:
        opts["domain"] = req.domain
    if req.userfile:
        opts["userfile"] = req.userfile
    result = await SprayRunner().run(req.target, opts)
    return _to_result(result, "spray")


# ---------------------------------------------------------------------------
# Hashcat
# ---------------------------------------------------------------------------

class HashcatRequest(BaseModel):
    target: str = Field(..., description="Hash file path or inline hash string")
    hash_type: int = Field(1000, description="Hashcat hash type: 1000=NTLM, 5600=NetNTLMv2, 18200=AS-REP/TGS, 13100=Kerberoast TGS")
    wordlist: str | None = Field(None, description="Wordlist path (uses rockyou.txt if available)")
    rules: str | None = Field(None, description="Hashcat rules file path")
    attack_mode: int = Field(0, description="Attack mode: 0=wordlist, 3=brute-force, 6=hybrid")
    timeout: int = Field(300, ge=30, le=3600, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/hashcat", response_model=ToolRunResult, summary="Hashcat offline password cracker")
async def run_hashcat(req: HashcatRequest) -> ToolRunResult:
    """Crack NTLM, NetNTLMv2, Kerberoast, or AS-REP hashes offline with wordlist or brute-force. MITRE T1110.002."""
    opts = dict(req.options)
    opts.update({
        "hash_type": req.hash_type,
        "attack_mode": req.attack_mode,
        "timeout": req.timeout,
    })
    if req.wordlist:
        opts["wordlist"] = req.wordlist
    if req.rules:
        opts["rules"] = req.rules
    result = await HashcatRunner().run(req.target, opts)
    return _to_result(result, "hashcat")


# ---------------------------------------------------------------------------
# Responder
# ---------------------------------------------------------------------------

class ResponderRequest(BaseModel):
    target: str = Field(..., description="Network interface (e.g. eth0) or subnet")
    interface: str = Field("eth0", description="Network interface to listen on")
    duration: int = Field(60, ge=10, le=600, description="Capture duration in seconds")
    active_poisoning: bool = Field(False, description="Enable active LLMNR/NBT-NS poisoning (requires root + PENTEST_ENABLE_ACTIVE_POISONING=true)")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/responder", response_model=ToolRunResult, summary="Responder LLMNR/NBT-NS poisoner")
async def run_responder(req: ResponderRequest) -> ToolRunResult:
    """Listen for and capture NTLM hashes via LLMNR/NBT-NS/mDNS poisoning. Requires root. MITRE T1557.001."""
    opts = dict(req.options)
    opts.update({
        "interface": req.interface,
        "duration": req.duration,
        "active_poisoning": req.active_poisoning,
    })
    result = await ResponderRunner().run(req.target, opts)
    return _to_result(result, "responder")
