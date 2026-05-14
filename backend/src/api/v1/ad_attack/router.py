"""AD Attack Tools — LDAP Recon, Ligolo-ng Pivoting, ACL Abuse, PtH/PtT, ADCS. Features 15-19."""
from __future__ import annotations
from typing import Any
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.ldap_recon_runner import LdapReconRunner
from src.adapters.scanners.pentest.ligolo_runner import LigoloRunner
from src.adapters.scanners.pentest.acl_abuse_runner import AclAbuseRunner
from src.adapters.scanners.pentest.pth_runner import PthRunner
from src.adapters.scanners.pentest.adcs_runner import AdcsRunner
from src.adapters.scanners.pentest.mitre_attack import get_mitre_techniques

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/ad-attack",
    tags=["ad-attack"],
    dependencies=[Depends(get_current_user)],
)


class FindingOut(BaseModel):
    tool: str; title: str; severity: str | None = None; description: str | None = None
    cvss_v3: float | None = None; cve: list[str] = []; cwe: int | None = None
    host: str | None = None; url: str | None = None
    evidence: dict[str, Any] = {}; mitre_techniques: list[str] = []


class ToolRunResult(BaseModel):
    tool: str; exit_code: int; duration_seconds: float
    findings: list[FindingOut]; findings_count: int = 0
    error: str | None = None; metadata: dict[str, Any] = {}


def _to_result(result: Any, tool_name: str = "") -> ToolRunResult:
    seen: set[str] = set()
    findings: list[FindingOut] = []
    for f in (result.findings or []):
        key = f"{f.title}|{f.host or ''}"
        if key in seen:
            continue
        seen.add(key)
        mitre = get_mitre_techniques(f.title, f.description, f.tool)
        findings.append(FindingOut(
            tool=f.tool, title=f.title, severity=f.severity, description=f.description,
            cvss_v3=f.cvss_v3, cve=f.cve, cwe=f.cwe, host=f.host,
            url=f.url, evidence=f.evidence, mitre_techniques=mitre,
        ))
    return ToolRunResult(
        tool=getattr(result, "tool", tool_name) or tool_name,
        exit_code=result.exit_code, duration_seconds=result.duration_seconds,
        findings=findings, findings_count=len(findings),
        error=result.error, metadata=getattr(result, "metadata", {}) or {},
    )


# ── Feature 15: LDAP Recon ────────────────────────────────────────────────────

class LdapReconRequest(BaseModel):
    target: str = Field(..., description="Domain controller IP or hostname")
    username: str = Field(..., description="AD username")
    password: str = Field(..., description="AD password")
    domain: str = Field(..., description="AD domain (e.g. corp.local)")
    port: int = Field(389, ge=389, le=3269)
    use_tls: bool = Field(False, description="Use LDAPS (port 636)")
    output_dir: str = Field("/tmp/ldap_recon", description="Output directory for dump files")
    timeout: int = Field(120, ge=30, le=600)


@router.post("/ldap-recon", response_model=ToolRunResult, summary="LDAP enumeration and AD domain dump")
async def run_ldap_recon(req: LdapReconRequest) -> ToolRunResult:
    """Enumerate AD users, groups, computers, GPOs, and ACLs via ldapdomaindump. Highlights privileged objects and weak configs."""
    result = await LdapReconRunner().run(req.target, req.model_dump())
    return _to_result(result, "ldap-recon")


# ── Feature 16: Ligolo-ng Pivoting ────────────────────────────────────────────

class LigoloRequest(BaseModel):
    proxy_addr: str = Field("0.0.0.0:11601", description="Proxy listen address")
    agent_target: str = Field("", description="IP:port where agent connects (leave blank = use proxy_addr IP)")
    tunnel_subnet: str = Field("192.168.1.0/24", description="Internal subnet to route through tunnel")
    tunnel_type: str = Field("reverse", description="Tunnel type: reverse|socks5|port_forward|full_vpn")
    tls: bool = Field(True, description="Use TLS (recommended)")
    certfile: str = Field("", description="TLS certificate path (blank = self-signed)")
    keyfile: str = Field("", description="TLS key path")
    interface: str = Field("ligolo", description="TUN interface name")
    port_fwd_local: str = Field("", description="Local port for port_forward mode")
    port_fwd_remote: str = Field("", description="Remote host:port for port_forward mode")


@router.post("/ligolo", response_model=ToolRunResult, summary="Ligolo-ng network pivoting command generator")
async def setup_ligolo(req: LigoloRequest) -> ToolRunResult:
    """Generate Ligolo-ng proxy/agent setup commands for reverse tunnels, SOCKS5 pivoting, and port forwarding."""
    result = await LigoloRunner().run(req.proxy_addr, req.model_dump())
    return _to_result(result, "ligolo-ng")


# ── Feature 17: ACL Abuse Analyzer ───────────────────────────────────────────

class AclAbuseRequest(BaseModel):
    target: str = Field(..., description="Domain controller IP")
    username: str = Field(..., description="AD username with read access")
    password: str = Field("", description="Password")
    domain: str = Field(..., description="AD domain")
    object_dn: str = Field("", description="Distinguished name of object to inspect (blank = domain root)")
    action: str = Field("enumerate", description="Action: enumerate|exploit")
    right: str = Field("", description="Right to grant for exploit mode (DCSync|GenericAll|etc)")
    target_dn: str = Field("", description="Target DN for shadow credential attack")
    timeout: int = Field(120, ge=30, le=600)


@router.post("/acl-abuse", response_model=ToolRunResult, summary="AD ACL abuse analyzer")
async def run_acl_abuse(req: AclAbuseRequest) -> ToolRunResult:
    """Enumerate and exploit AD ACL misconfigurations: WriteDACL, GenericAll, DCSync paths, shadow credentials."""
    result = await AclAbuseRunner().run(req.target, req.model_dump())
    return _to_result(result, "acl-abuse")


# ── Feature 18: Pass-the-Hash / Pass-the-Ticket ───────────────────────────────

class PthRequest(BaseModel):
    target: str = Field(..., description="Target host IP or hostname")
    username: str = Field(..., description="Username")
    nt_hash: str = Field("", description="NT hash for Pass-the-Hash (32 hex chars)")
    ticket_path: str = Field("", description=".ccache ticket path for Pass-the-Ticket")
    domain: str = Field("", description="Domain")
    command: str = Field("whoami", description="Command to execute remotely")
    tool: str = Field("wmiexec", description="Impacket tool: wmiexec|psexec|smbexec|atexec")
    timeout: int = Field(60, ge=10, le=300)


@router.post("/pth", response_model=ToolRunResult, summary="Pass-the-Hash / Pass-the-Ticket lateral movement")
async def run_pth(req: PthRequest) -> ToolRunResult:
    """Lateral movement via NTLM hash (PtH) or Kerberos ticket (PtT) using Impacket tools."""
    result = await PthRunner().run(req.target, req.model_dump())
    return _to_result(result, "pth")


# ── Feature 19: ADCS Attack Suite ────────────────────────────────────────────

class AdcsRequest(BaseModel):
    target: str = Field(..., description="Domain controller IP")
    username: str = Field(..., description="AD username")
    password: str = Field("", description="Password")
    domain: str = Field(..., description="AD domain")
    action: str = Field("find", description="Action: find|req|auth|shadow")
    ca: str = Field("", description="Certificate Authority name")
    template: str = Field("", description="Certificate template name")
    upn: str = Field("", description="Target UPN for ESC1 (e.g. administrator@domain.local)")
    account: str = Field("", description="Target account for shadow credentials")
    dc_ip: str = Field("", description="DC IP (defaults to target)")
    timeout: int = Field(120, ge=30, le=600)


@router.post("/adcs", response_model=ToolRunResult, summary="ADCS ESC1-ESC8 attack suite")
async def run_adcs(req: AdcsRequest) -> ToolRunResult:
    """Enumerate and exploit Active Directory Certificate Services misconfigurations (ESC1-ESC8) via Certipy."""
    result = await AdcsRunner().run(req.target, req.model_dump())
    return _to_result(result, "certipy")
