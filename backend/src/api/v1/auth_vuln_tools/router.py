"""Auth & Web Vuln Tools API — Hydra, Medusa, JWT, OAuth, DefaultCreds, SSRF, XXE, SSTI, CORS, GraphQL."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.hydra_runner import HydraRunner, SUPPORTED_SERVICES
from src.adapters.scanners.pentest.medusa_runner import MedusaRunner
from src.adapters.scanners.pentest.jwt_attack_runner import JWTAttackRunner
from src.adapters.scanners.pentest.oauth_tester_runner import OAuthTesterRunner
from src.adapters.scanners.pentest.default_creds_runner import DefaultCredsRunner
from src.adapters.scanners.pentest.ssrf_scanner_runner import SSRFScannerRunner
from src.adapters.scanners.pentest.xxe_scanner_runner import XXEScannerRunner
from src.adapters.scanners.pentest.ssti_scanner_runner import SSTIScannerRunner
from src.adapters.scanners.pentest.cors_tester_runner import CORSTesterRunner
from src.adapters.scanners.pentest.graphql_scanner_runner import GraphQLScannerRunner

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/auth-vuln-tools",
    tags=["auth-vuln-tools"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Shared output schemas (reused from batch 1 pattern)
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
        metadata=result.metadata if hasattr(result, "metadata") and result.metadata else {},
    )


# ---------------------------------------------------------------------------
# Hydra
# ---------------------------------------------------------------------------

class HydraRequest(BaseModel):
    target: str = Field(..., description="Target hostname or IP")
    service: str = Field("ssh", description=f"Service to attack. Supported: {', '.join(sorted(SUPPORTED_SERVICES))}")
    userlist: str | None = Field(None, description="Path to username wordlist")
    passlist: str | None = Field(None, description="Path to password wordlist")
    user: str | None = Field(None, description="Single username")
    password: str | None = Field(None, description="Single password")
    threads: int = Field(4, ge=1, le=16)
    form_string: str | None = Field(None, description="For http-post-form: '/login:user=^USER^&pass=^PASS^:F=invalid'")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/hydra", response_model=ToolRunResult, summary="Hydra login brute-forcer")
async def run_hydra(req: HydraRequest) -> ToolRunResult:
    """Brute-force login credentials across SSH, FTP, HTTP, SMB, RDP and more."""
    opts = dict(req.options)
    for k in ("userlist", "passlist", "user", "password", "threads", "form_string", "service"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await HydraRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Medusa
# ---------------------------------------------------------------------------

class MedusaRequest(BaseModel):
    target: str
    module: str = Field("ssh", description="Medusa module (ssh, ftp, smb, http, ldap, mssql, mysql)")
    userlist: str | None = None
    passlist: str | None = None
    user: str | None = None
    password: str | None = None
    port: int | None = None
    threads: int = Field(4, ge=1, le=16)
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/medusa", response_model=ToolRunResult, summary="Medusa parallel login auditor")
async def run_medusa(req: MedusaRequest) -> ToolRunResult:
    """Parallel brute-force across multiple hosts/services simultaneously."""
    opts = dict(req.options)
    for k in ("module", "userlist", "passlist", "user", "password", "port", "threads"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await MedusaRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# JWT Attack Suite
# ---------------------------------------------------------------------------

class JWTAttackRequest(BaseModel):
    token: str = Field(..., description="JWT token string to analyze")
    wordlist: str | None = Field(None, description="Path to secret wordlist for HS256 brute-force")
    public_key: str | None = Field(None, description="PEM public key for RS→HS confusion check")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/jwt-attack", response_model=ToolRunResult, summary="JWT vulnerability scanner")
async def run_jwt_attack(req: JWTAttackRequest) -> ToolRunResult:
    """Analyze a JWT token for alg:none, weak secrets, missing expiry, sensitive payload data."""
    opts = dict(req.options)
    if req.wordlist:
        opts["wordlist"] = req.wordlist
    if req.public_key:
        opts["public_key"] = req.public_key
    result = await JWTAttackRunner().run(req.token, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# OAuth Tester
# ---------------------------------------------------------------------------

class OAuthRequest(BaseModel):
    authorization_endpoint: str = Field(..., description="OAuth authorization endpoint URL")
    client_id: str = Field("test_client", description="OAuth client_id to use in probes")
    redirect_uri: str = Field("https://localhost/callback", description="Registered redirect_uri")
    token_endpoint: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/oauth-tester", response_model=ToolRunResult, summary="OAuth 2.0 misconfiguration tester")
async def run_oauth_tester(req: OAuthRequest) -> ToolRunResult:
    """Test OAuth endpoints for open redirects, missing PKCE, implicit flow, state CSRF."""
    opts = dict(req.options)
    opts["client_id"] = req.client_id
    opts["redirect_uri"] = req.redirect_uri
    if req.token_endpoint:
        opts["token_endpoint"] = req.token_endpoint
    result = await OAuthTesterRunner().run(req.authorization_endpoint, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# Default Credentials
# ---------------------------------------------------------------------------

class DefaultCredsRequest(BaseModel):
    target: str = Field(..., description="Target URL (web login page)")
    login_path: str = Field("", description="Login endpoint path (e.g. /admin/login)")
    user_field: str = Field("username", description="Form username field name")
    pass_field: str = Field("password", description="Form password field name")
    success_indicator: str = Field("", description="Text present on successful login")
    failure_indicator: str = Field("invalid", description="Text present on failed login")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/default-creds", response_model=ToolRunResult, summary="Default credential checker")
async def run_default_creds(req: DefaultCredsRequest) -> ToolRunResult:
    """Test web login forms and HTTP Basic Auth against common default credential pairs."""
    opts = dict(req.options)
    for k in ("login_path", "user_field", "pass_field", "success_indicator", "failure_indicator"):
        v = getattr(req, k, None)
        if v is not None:
            opts[k] = v
    result = await DefaultCredsRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# SSRF Scanner
# ---------------------------------------------------------------------------

class SSRFRequest(BaseModel):
    target: str = Field(..., description="Target URL (may include query params)")
    params: list[str] = Field(default_factory=list, description="Parameter names to test (auto-detected if empty)")
    interactsh_url: str | None = Field(None, description="Interactsh OOB callback URL for blind SSRF")
    cookie: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/ssrf", response_model=ToolRunResult, summary="SSRF vulnerability scanner")
async def run_ssrf(req: SSRFRequest) -> ToolRunResult:
    """Inject internal metadata service URLs into URL parameters to detect SSRF."""
    opts = dict(req.options)
    if req.params:
        opts["params"] = req.params
    if req.interactsh_url:
        opts["interactsh_url"] = req.interactsh_url
    if req.cookie:
        opts["cookie"] = req.cookie
    result = await SSRFScannerRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# XXE Scanner
# ---------------------------------------------------------------------------

class XXERequest(BaseModel):
    target: str = Field(..., description="Target base URL")
    method: str = Field("POST", description="HTTP method for injection")
    paths: list[str] = Field(default_factory=list, description="Paths to probe (uses common defaults if empty)")
    interactsh_url: str | None = Field(None, description="OOB callback for blind XXE")
    cookie: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/xxe", response_model=ToolRunResult, summary="XXE injection scanner")
async def run_xxe(req: XXERequest) -> ToolRunResult:
    """Inject XXE payloads into XML endpoints to test for file read and SSRF."""
    opts = dict(req.options)
    opts["method"] = req.method
    if req.paths:
        opts["paths"] = req.paths
    if req.interactsh_url:
        opts["interactsh_url"] = req.interactsh_url
    if req.cookie:
        opts["cookie"] = req.cookie
    result = await XXEScannerRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# SSTI Scanner
# ---------------------------------------------------------------------------

class SSTIRequest(BaseModel):
    target: str = Field(..., description="Target URL with or without query params")
    params: list[str] = Field(default_factory=list, description="Parameter names to test")
    data: str | None = Field(None, description="POST data for tplmap")
    cookie: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/ssti", response_model=ToolRunResult, summary="SSTI scanner")
async def run_ssti(req: SSTIRequest) -> ToolRunResult:
    """Detect Server-Side Template Injection across Jinja2, Twig, Freemarker, Pebble, ERB, Spring EL."""
    opts = dict(req.options)
    if req.params:
        opts["params"] = req.params
    if req.data:
        opts["data"] = req.data
    if req.cookie:
        opts["cookie"] = req.cookie
    result = await SSTIScannerRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# CORS Tester
# ---------------------------------------------------------------------------

class CORSRequest(BaseModel):
    target: str = Field(..., description="Target base URL")
    paths: list[str] = Field(default_factory=list, description="Paths to test CORS on")
    cookie: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/cors", response_model=ToolRunResult, summary="CORS misconfiguration tester")
async def run_cors(req: CORSRequest) -> ToolRunResult:
    """Test CORS policy for origin reflection, null origin, wildcard+credentials misconfigurations."""
    opts = dict(req.options)
    if req.paths:
        opts["paths"] = req.paths
    if req.cookie:
        opts["cookie"] = req.cookie
    result = await CORSTesterRunner().run(req.target, opts)
    return _to_result(result)


# ---------------------------------------------------------------------------
# GraphQL Scanner
# ---------------------------------------------------------------------------

class GraphQLRequest(BaseModel):
    target: str = Field(..., description="Target base URL")
    endpoint: str | None = Field(None, description="GraphQL endpoint path (auto-discovered if omitted)")
    cookie: str | None = None
    auth_header: str | None = Field(None, description="Authorization header value")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/graphql", response_model=ToolRunResult, summary="GraphQL security scanner")
async def run_graphql(req: GraphQLRequest) -> ToolRunResult:
    """Probe GraphQL for introspection leakage, field suggestions, batching DoS, depth limits, CSRF via GET."""
    opts = dict(req.options)
    if req.endpoint:
        opts["endpoint"] = req.endpoint
    if req.cookie:
        opts["cookie"] = req.cookie
    if req.auth_header:
        opts["auth_header"] = req.auth_header
    result = await GraphQLScannerRunner().run(req.target, opts)
    return _to_result(result)
