"""Web Attack Tools API — Nikto, WPScan, Commix, XSSer, wfuzz, dirsearch, Skipfish, SQLNinja, Masscan, BeEF."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.nikto_runner import NiktoRunner
from src.adapters.scanners.pentest.wpscan_runner import WPScanRunner
from src.adapters.scanners.pentest.commix_runner import CommixRunner
from src.adapters.scanners.pentest.xsser_runner import XSSerRunner
from src.adapters.scanners.pentest.wfuzz_runner import WfuzzRunner
from src.adapters.scanners.pentest.dirsearch_runner import DirsearchRunner
from src.adapters.scanners.pentest.skipfish_runner import SkipfishRunner
from src.adapters.scanners.pentest.sqlninja_runner import SQLNinjaRunner
from src.adapters.scanners.pentest.masscan_runner import MasscanRunner
from src.adapters.scanners.pentest.beef_runner import BeEFRunner

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/web-attack-tools",
    tags=["web-attack-tools"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Shared schemas
# ---------------------------------------------------------------------------

class ToolRunRequest(BaseModel):
    target: str = Field(..., description="Target URL, IP, or hostname")
    options: dict[str, Any] = Field(default_factory=dict, description="Tool-specific options")


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


def _to_result(result: Any) -> ToolRunResult:
    findings = [
        FindingOut(
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
    )


# ---------------------------------------------------------------------------
# Nikto
# ---------------------------------------------------------------------------

@router.post("/nikto", response_model=ToolRunResult, summary="Nikto web server scanner")
async def run_nikto(req: ToolRunRequest) -> ToolRunResult:
    """Scan a web server with Nikto for misconfigurations, outdated software, and dangerous files."""
    result = await NiktoRunner().run(req.target, req.options)
    return _to_result(result)


# ---------------------------------------------------------------------------
# WPScan
# ---------------------------------------------------------------------------

class WPScanRequest(ToolRunRequest):
    api_token: str | None = Field(None, description="WPScan API token for CVE lookups")
    enumerate: str = Field("vp,vt,u", description="WPScan enumeration options")


@router.post("/wpscan", response_model=ToolRunResult, summary="WPScan WordPress scanner")
async def run_wpscan(req: WPScanRequest) -> ToolRunResult:
    """Enumerate WordPress plugins, themes, and users; match against vulnerability database."""
    opts = dict(req.options)
    if req.api_token:
        opts["api_token"] = req.api_token
    opts["enumerate"] = req.enumerate
    result = await WPScanRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Commix
# ---------------------------------------------------------------------------

class CommixRequest(ToolRunRequest):
    data: str | None = Field(None, description="POST data (use * to mark injection point)")
    cookie: str | None = None
    headers: str | None = None
    technique: str = Field("c", description="Injection technique: c=classic, t=time, f=file")
    level: int = Field(1, ge=1, le=3)


@router.post("/commix", response_model=ToolRunResult, summary="Commix command injection scanner")
async def run_commix(req: CommixRequest) -> ToolRunResult:
    """Detect OS command injection vulnerabilities in web application parameters."""
    opts = dict(req.options)
    for k in ("data", "cookie", "headers", "technique", "level"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await CommixRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# XSSer
# ---------------------------------------------------------------------------

class XSSerRequest(ToolRunRequest):
    data: str | None = Field(None, description="POST data")
    cookie: str | None = None
    headers: str | None = None


@router.post("/xsser", response_model=ToolRunResult, summary="XSSer cross-site scripting scanner")
async def run_xsser(req: XSSerRequest) -> ToolRunResult:
    """Detect reflected and DOM-based XSS vulnerabilities automatically."""
    opts = dict(req.options)
    for k in ("data", "cookie", "headers"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await XSSerRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# wfuzz
# ---------------------------------------------------------------------------

class WfuzzRequest(ToolRunRequest):
    wordlist: str | None = Field(None, description="Path to wordlist (uses SecLists default if omitted)")
    hide_codes: str = Field("404", description="Comma-separated HTTP codes to hide (e.g. 404,403)")
    cookie: str | None = None
    threads: int = Field(10, ge=1, le=50)


@router.post("/wfuzz", response_model=ToolRunResult, summary="wfuzz web fuzzer")
async def run_wfuzz(req: WfuzzRequest) -> ToolRunResult:
    """Fuzz URL paths and parameters to discover hidden endpoints and files.

    Append FUZZ to the target URL to control injection point, e.g. http://target.com/FUZZ
    """
    opts = dict(req.options)
    for k in ("wordlist", "hide_codes", "cookie", "threads"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await WfuzzRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# dirsearch
# ---------------------------------------------------------------------------

class DirsearchRequest(ToolRunRequest):
    extensions: str = Field("php,html,js,txt,asp,aspx,jsp", description="File extensions to try")
    threads: int = Field(20, ge=1, le=50)
    wordlist: str | None = None
    exclude_status: str | None = Field(None, description="Exclude status codes, e.g. 404,403")


@router.post("/dirsearch", response_model=ToolRunResult, summary="dirsearch directory brute-force")
async def run_dirsearch(req: DirsearchRequest) -> ToolRunResult:
    """Brute-force directories and files on a web server with extension permutations."""
    opts = dict(req.options)
    for k in ("extensions", "threads", "wordlist", "exclude_status"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await DirsearchRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Skipfish
# ---------------------------------------------------------------------------

class SkipfishRequest(ToolRunRequest):
    max_requests: int = Field(2000, ge=100, le=20000)
    max_depth: int = Field(5, ge=1, le=15)
    cookie: str | None = None
    auth_form: str | None = Field(None, description="Form-based auth: url:user=x&pass=y")


@router.post("/skipfish", response_model=ToolRunResult, summary="Skipfish active web recon")
async def run_skipfish(req: SkipfishRequest) -> ToolRunResult:
    """Run Skipfish recursive web crawler with active injection probing."""
    opts = dict(req.options)
    for k in ("max_requests", "max_depth", "cookie", "auth_form"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await SkipfishRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# SQLNinja
# ---------------------------------------------------------------------------

class SQLNinjaRequest(ToolRunRequest):
    post_data: str | None = Field(None, description="POST parameters")
    cookie: str | None = None
    vuln_param: str | None = Field(None, description="Vulnerable parameter name")


@router.post("/sqlninja", response_model=ToolRunResult, summary="SQLNinja MS-SQL injection scanner")
async def run_sqlninja(req: SQLNinjaRequest) -> ToolRunResult:
    """Detect SQL injection in Microsoft SQL Server applications (fingerprint mode)."""
    opts = dict(req.options)
    for k in ("post_data", "cookie", "vuln_param"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await SQLNinjaRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Masscan
# ---------------------------------------------------------------------------

class MasscanRequest(BaseModel):
    target: str = Field(..., description="IP address or CIDR range (e.g. 192.168.1.0/24)")
    ports: str = Field("0-1024,3306,5432,6379,8080,8443,27017", description="Port range to scan")
    rate: int = Field(1000, ge=100, le=10000, description="Packets per second (capped at 10000)")
    banners: bool = Field(False, description="Enable banner grabbing")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/masscan", response_model=ToolRunResult, summary="Masscan fast port scanner")
async def run_masscan(req: MasscanRequest) -> ToolRunResult:
    """Perform high-speed port scanning. Requires root/CAP_NET_RAW in the container."""
    opts = dict(req.options)
    opts["ports"] = req.ports
    opts["rate"] = req.rate
    opts["banners"] = req.banners
    result = await MasscanRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# BeEF
# ---------------------------------------------------------------------------

class BeEFRequest(BaseModel):
    beef_url: str = Field("http://localhost:3000", description="BeEF REST API base URL")
    api_token: str | None = Field(None, description="BeEF API token (auto-auth if omitted)")
    user: str = Field("beef", description="BeEF username for auto-auth")
    password: str = Field("beef", description="BeEF password for auto-auth")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/beef", response_model=ToolRunResult, summary="BeEF hooked browser enumeration")
async def run_beef(req: BeEFRequest) -> ToolRunResult:
    """Connect to a running BeEF instance and enumerate hooked browsers and collected data."""
    opts = dict(req.options)
    opts["beef_url"] = req.beef_url
    if req.api_token:
        opts["api_token"] = req.api_token
    opts["user"] = req.user
    opts["password"] = req.password
    result = await BeEFRunner().run("beef", opts)
    return _to_result(result)
