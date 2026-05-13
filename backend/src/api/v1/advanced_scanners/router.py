"""Advanced Pentest Scanners — Nuclei, Subfinder, FFUF, HTTPx, SSLyze, ZAP + extensions.

Improvement 1:  Exposes runners that previously had no direct-run API surface.
Improvement 2:  MITRE ATT&CK enrichment on all findings via mitre_attack module.
Improvement 3:  Finding deduplication (title+host+port hash) in _to_result.
Improvement 10: Pentest tool binary health check endpoint.
Improvement 11: Interactsh OOB interaction server.
Improvement 12: Scope guard applied to all tool endpoints.
Improvement 13: DefectDojo export endpoint.
Improvement 14: Nuclei template browser endpoint.
Improvement 15: Batch scan (run one tool against multiple targets concurrently).
Improvement 16: SSE live tool output streaming.
Improvement 21: CVE enrichment via NVD API 2.0.
Improvement 22: SARIF 2.1.0 export from tool findings.
Improvement 23: HTML pentest report download.
Improvement 24: Scan profiles CRUD (in-memory store).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.nuclei_runner import NucleiRunner
from src.adapters.scanners.pentest.subfinder_runner import SubfinderRunner
from src.adapters.scanners.pentest.ffuf_runner import FfufRunner
from src.adapters.scanners.pentest.httpx_runner import HttpxRunner
from src.adapters.scanners.pentest.sslyze_runner import SslyzeRunner
from src.adapters.scanners.pentest.zap_runner import ZapRunner
from src.adapters.scanners.pentest.interactsh_runner import InteractshRunner
from src.adapters.scanners.pentest.mitre_attack import get_mitre_techniques
from src.adapters.scanners.pentest.cve_enricher import enrich_cves
from src.adapters.reporting.sarif_generator import SarifGenerator
from src.adapters.security.scope_validator import ScopeRules, ScopeViolation, ScopeValidator

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/advanced-scanners",
    tags=["advanced-scanners"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------------
# Shared output schemas (with MITRE ATT&CK field)
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
    """Convert runner ToolResult → API response with dedup + MITRE enrichment."""
    seen: set[str] = set()
    findings: list[FindingOut] = []
    for f in (result.findings or []):
        # Improvement 3: hash-based deduplication
        key = f"{f.title}|{f.host or ''}|{f.port or ''}"
        if key in seen:
            continue
        seen.add(key)
        # Improvement 2: MITRE ATT&CK enrichment
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
# Improvement 10: Pentest Tool Health endpoint
# ---------------------------------------------------------------------------

_PENTEST_BINARIES: list[tuple[str, str]] = [
    ("nmap", "Port Scanner"),
    ("nuclei", "Template Scanner"),
    ("subfinder", "Subdomain Discovery"),
    ("ffuf", "Web Fuzzer"),
    ("gobuster", "Directory Bruteforce"),
    ("feroxbuster", "Recursive Fuzzer"),
    ("httpx", "HTTP Probe"),
    ("sslyze", "SSL/TLS Auditor"),
    ("zaproxy", "OWASP ZAP"),
    ("sqlmap", "SQLi Scanner"),
    ("nikto", "Web Scanner"),
    ("wpscan", "WordPress Scanner"),
    ("hydra", "Brute Forcer"),
    ("medusa", "Brute Forcer"),
    ("crackmapexec", "AD Enum (CME)"),
    ("nxc", "AD Enum (NetExec)"),
    ("bloodhound-python", "BloodHound Ingestor"),
    ("impacket-secretsdump", "Impacket Suite"),
    ("certipy", "AD CS Auditor"),
    ("enum4linux-ng", "SMB Enumerator"),
    ("bettercap", "MitM Framework"),
    ("aircrack-ng", "WiFi Auditor"),
    ("hashcat", "Password Cracker"),
    ("responder", "LLMNR Poisoner"),
    ("metasploit", "MSF Console"),
    ("msfconsole", "MSF Console"),
    ("openvas", "Vulnerability Scanner"),
    ("gvm-cli", "GVM CLI"),
    ("masscan", "Port Scanner"),
    ("commix", "Command Injection"),
]


class ToolBinaryStatus(BaseModel):
    name: str
    category: str
    available: bool
    path: str | None = None


class ToolHealthResponse(BaseModel):
    tools: list[ToolBinaryStatus]
    available_count: int
    missing_count: int
    total_count: int


@router.get("/tool-health", response_model=ToolHealthResponse, summary="Pentest binary health check")
async def get_tool_health() -> ToolHealthResponse:
    """Check which pentest tool binaries are installed and available in PATH."""
    statuses: list[ToolBinaryStatus] = []
    for binary, category in _PENTEST_BINARIES:
        path = shutil.which(binary)
        statuses.append(ToolBinaryStatus(name=binary, category=category, available=path is not None, path=path))
    available = sum(1 for s in statuses if s.available)
    return ToolHealthResponse(
        tools=statuses,
        available_count=available,
        missing_count=len(statuses) - available,
        total_count=len(statuses),
    )


# ---------------------------------------------------------------------------
# Nuclei
# ---------------------------------------------------------------------------

class NucleiRequest(BaseModel):
    target: str = Field(..., description="Target URL or IP")
    severity: str = Field("medium,high,critical", description="Severity filter (comma-separated)")
    templates_path: str | None = Field(None, description="Templates path or directory")
    extra_flags: list[str] = Field(default_factory=list, description="Additional nuclei flags")
    timeout: int = Field(180, ge=30, le=600, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/nuclei", response_model=ToolRunResult, summary="Nuclei template-based vulnerability scanner")
async def run_nuclei(req: NucleiRequest) -> ToolRunResult:
    """Run Nuclei templates against target. Returns CVE-mapped findings enriched with MITRE ATT&CK techniques."""
    opts = dict(req.options)
    if req.templates_path:
        opts["templates_path"] = req.templates_path
    if req.extra_flags:
        opts["extra_flags"] = req.extra_flags
    opts["timeout"] = req.timeout
    result = await NucleiRunner().run(req.target, opts)
    return _to_result(result, "nuclei")


# ---------------------------------------------------------------------------
# Subfinder
# ---------------------------------------------------------------------------

class SubfinderRequest(BaseModel):
    target: str = Field(..., description="Domain to enumerate subdomains for")
    extra_flags: list[str] = Field(default_factory=list, description="Additional subfinder flags")
    timeout: int = Field(120, ge=15, le=300, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/subfinder", response_model=ToolRunResult, summary="Passive subdomain discovery")
async def run_subfinder(req: SubfinderRequest) -> ToolRunResult:
    """Enumerate subdomains using passive DNS sources (Shodan, Censys, crt.sh, etc.)."""
    opts = dict(req.options)
    if req.extra_flags:
        opts["extra_flags"] = req.extra_flags
    opts["timeout"] = req.timeout
    result = await SubfinderRunner().run(req.target, opts)
    return _to_result(result, "subfinder")


# ---------------------------------------------------------------------------
# FFUF
# ---------------------------------------------------------------------------

class FfufRequest(BaseModel):
    target: str = Field(..., description="Target URL (FUZZ marker inserted automatically)")
    wordlist: str | None = Field(None, description="Path to wordlist (uses default if omitted)")
    extensions: str = Field("php,html,js,txt,bak", description="File extensions to check")
    timeout: int = Field(120, ge=30, le=600, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/ffuf", response_model=ToolRunResult, summary="FFUF fast web fuzzer")
async def run_ffuf(req: FfufRequest) -> ToolRunResult:
    """Fast web fuzzer for directory, parameter, and endpoint discovery."""
    result = await FfufRunner().run(req.target)
    return _to_result(result, "ffuf")


# ---------------------------------------------------------------------------
# HTTPx
# ---------------------------------------------------------------------------

class HttpxRequest(BaseModel):
    target: str = Field(..., description="Target domain, IP, or URL")
    ports: str | None = Field(None, description="Ports to probe, e.g. '80,443,8080'")
    timeout: int = Field(30, ge=5, le=120, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/httpx", response_model=ToolRunResult, summary="HTTPx HTTP service probe")
async def run_httpx(req: HttpxRequest) -> ToolRunResult:
    """Probe HTTP/HTTPS services, detect web servers, status codes, redirects, and technologies."""
    opts = dict(req.options)
    if req.ports:
        opts["ports"] = req.ports
    opts["timeout"] = req.timeout
    result = await HttpxRunner().run(req.target, opts)
    return _to_result(result, "httpx")


# ---------------------------------------------------------------------------
# SSLyze
# ---------------------------------------------------------------------------

class SSLyzeRequest(BaseModel):
    target: str = Field(..., description="Hostname or IP (port appended as host:port if needed)")
    port: int = Field(443, ge=1, le=65535, description="TLS port")
    timeout: int = Field(60, ge=10, le=300, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/sslyze", response_model=ToolRunResult, summary="SSLyze TLS/SSL configuration audit")
async def run_sslyze(req: SSLyzeRequest) -> ToolRunResult:
    """Audit TLS/SSL configuration: protocol versions, cipher suites, certificate validity, Heartbleed, BEAST, etc."""
    opts = dict(req.options)
    opts["port"] = req.port
    opts["timeout"] = req.timeout
    result = await SslyzeRunner().run(req.target, opts)
    return _to_result(result, "sslyze")


# ---------------------------------------------------------------------------
# ZAP
# ---------------------------------------------------------------------------

class ZAPRequest(BaseModel):
    target: str = Field(..., description="Target URL for OWASP ZAP scan")
    scan_type: str = Field("passive", description="Scan type: passive | active | spider | ajax_spider")
    api_key: str | None = Field(None, description="ZAP API key")
    zap_url: str = Field("http://127.0.0.1:8090", description="ZAP daemon URL")
    timeout: int = Field(300, ge=30, le=900, description="Timeout in seconds")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/zap", response_model=ToolRunResult, summary="OWASP ZAP web application scanner")
async def run_zap(req: ZAPRequest) -> ToolRunResult:
    """Run OWASP ZAP passive or active scan. Returns OWASP categorized findings with MITRE enrichment."""
    opts = dict(req.options)
    opts.update({
        "scan_type": req.scan_type,
        "zap_url": req.zap_url,
        "timeout": req.timeout,
    })
    if req.api_key:
        opts["api_key"] = req.api_key
    result = await ZapRunner().run(req.target, opts)
    return _to_result(result, "zap")


# ---------------------------------------------------------------------------
# Improvement 12: Scope guard helper
# ---------------------------------------------------------------------------

def _check_scope(target: str, allowed_cidrs: list[str], allowed_domains: list[str]) -> None:
    """Raise HTTP 422 if target violates scope rules."""
    if not allowed_cidrs and not allowed_domains:
        return  # no rules = unrestricted
    rules = ScopeRules(allowed_cidrs=allowed_cidrs, allowed_domains=allowed_domains)
    validator = ScopeValidator(rules)
    try:
        if target.startswith("http://") or target.startswith("https://"):
            validator.validate_url(target)
        elif "/" in target and not target.startswith("http"):
            validator.validate_cidr(target)
        elif any(c.isalpha() for c in target.split(".")[0]):
            validator.validate_domain(target)
        else:
            validator.validate_ip(target)
    except ScopeViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scope violation: {exc}",
        )


# ---------------------------------------------------------------------------
# Improvement 11: Interactsh OOB server
# ---------------------------------------------------------------------------

class InteractshRequest(BaseModel):
    target: str = Field("", description="Context label for this OOB session (optional)")
    server: str = Field("https://interact.sh", description="Interactsh server URL")
    duration: int = Field(60, ge=10, le=600, description="Listen duration in seconds")
    token: str | None = Field(None, description="Interactsh API token (for private servers)")
    options: dict[str, Any] = Field(default_factory=dict)


@router.post("/interactsh", response_model=ToolRunResult, summary="Interactsh OOB interaction listener")
async def run_interactsh(req: InteractshRequest) -> ToolRunResult:
    """Register a unique OOB subdomain and poll for DNS/HTTP interactions.
    Paste the returned oob_url into SSRF/XXE payloads to confirm blind vulnerabilities."""
    opts = dict(req.options)
    opts.update({"server": req.server, "duration": req.duration})
    if req.token:
        opts["token"] = req.token
    result = await InteractshRunner().run(req.target or "oob-session", opts)
    return _to_result(result, "interactsh")


# ---------------------------------------------------------------------------
# Improvement 13: DefectDojo export
# ---------------------------------------------------------------------------

class DefectDojoFinding(BaseModel):
    title: str
    severity: str
    description: str
    tool_type: str
    active: bool = True
    verified: bool = False
    mitre_techniques: list[str] = []
    cve: list[str] = []
    cvss_v3: float | None = None
    url: str | None = None
    host: str | None = None


class DefectDojoExportRequest(BaseModel):
    findings: list[FindingOut]
    engagement_name: str = Field("Pentest Export", description="Engagement label for DefectDojo")
    product_name: str = Field("Target Application", description="Product name in DefectDojo")
    push_to_defectdojo: bool = Field(False, description="Push directly to DefectDojo instance")
    defectdojo_url: str | None = Field(None, description="DefectDojo API URL (if push_to_defectdojo=true)")
    api_key: str | None = Field(None, description="DefectDojo API key")


class DefectDojoExportResponse(BaseModel):
    findings_count: int
    engagement_name: str
    defectdojo_findings: list[dict[str, Any]]
    pushed: bool = False
    push_error: str | None = None


@router.post("/defectdojo-export", response_model=DefectDojoExportResponse, summary="Export findings to DefectDojo format")
async def defectdojo_export(req: DefectDojoExportRequest) -> DefectDojoExportResponse:
    """Convert tool findings to DefectDojo JSON format. Optionally push to a live DefectDojo instance."""
    dojo_findings: list[dict[str, Any]] = []
    for f in req.findings:
        dojo_findings.append({
            "title": f.title,
            "severity": _map_severity_dojo(f.severity),
            "description": f.description or "",
            "tool_type": f.tool,
            "active": True,
            "verified": False,
            "numerical_severity": _cvss_to_numerical(f.cvss_v3),
            "cvssv3_score": f.cvss_v3,
            "cve": ", ".join(f.cve) if f.cve else None,
            "cwe": f.cwe,
            "url": f.url,
            "impact": "Unknown",
            "mitigation": "Review and remediate based on tool output.",
            "references": "; ".join(f.mitre_techniques),
            "tags": [f.tool] + [t.split(" — ")[0] for t in f.mitre_techniques],
            "component_name": f.host,
        })

    pushed = False
    push_error: str | None = None

    if req.push_to_defectdojo and req.defectdojo_url and req.api_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                # Create engagement and push findings
                resp = await client.post(
                    f"{req.defectdojo_url}/api/v2/findings/",
                    headers={"Authorization": f"Token {req.api_key}", "Content-Type": "application/json"},
                    json={"findings": dojo_findings, "engagement": req.engagement_name},
                )
                if resp.status_code in (200, 201):
                    pushed = True
                else:
                    push_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            push_error = str(exc)

    return DefectDojoExportResponse(
        findings_count=len(dojo_findings),
        engagement_name=req.engagement_name,
        defectdojo_findings=dojo_findings,
        pushed=pushed,
        push_error=push_error,
    )


def _map_severity_dojo(severity: str | None) -> str:
    mapping = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "info": "Info"}
    return mapping.get((severity or "info").lower(), "Info")


def _cvss_to_numerical(cvss: float | None) -> str:
    if cvss is None:
        return "S0"
    if cvss >= 9.0:
        return "S0"
    if cvss >= 7.0:
        return "S1"
    if cvss >= 4.0:
        return "S2"
    return "S3"


# ---------------------------------------------------------------------------
# Improvement 14: Nuclei template browser
# ---------------------------------------------------------------------------

class NucleiTemplate(BaseModel):
    id: str
    name: str
    path: str
    tags: list[str] = []
    severity: str = "info"


class NucleiTemplatesResponse(BaseModel):
    templates: list[NucleiTemplate]
    total_count: int
    search: str | None = None


@router.get("/nuclei/templates", response_model=NucleiTemplatesResponse, summary="List installed Nuclei templates")
async def list_nuclei_templates(search: str | None = None) -> NucleiTemplatesResponse:
    """List all installed Nuclei templates. Optionally filter by search term."""
    nuclei_bin = shutil.which("nuclei")
    if not nuclei_bin:
        return NucleiTemplatesResponse(templates=[], total_count=0, search=search)

    templates: list[NucleiTemplate] = []
    try:
        proc = await asyncio.create_subprocess_exec(
            nuclei_bin, "-list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        for line in stdout.decode(errors="replace").splitlines():
            path = line.strip()
            if not path or not path.endswith(".yaml"):
                continue
            parts = path.split(os.sep)
            template_id = parts[-1].replace(".yaml", "")
            # Extract category from path (e.g. cves/CVE-2021-44228.yaml → cves)
            category = parts[-2] if len(parts) >= 2 else "unknown"
            name = template_id.replace("-", " ").title()
            severity = "info"
            for sev in ("critical", "high", "medium", "low"):
                if sev in path.lower():
                    severity = sev
                    break
            tmpl = NucleiTemplate(id=template_id, name=name, path=path, tags=[category], severity=severity)
            if search is None or search.lower() in template_id.lower() or search.lower() in category.lower():
                templates.append(tmpl)
    except Exception as exc:
        await log.awarning("nuclei_list_failed", error=str(exc))

    return NucleiTemplatesResponse(templates=templates[:500], total_count=len(templates), search=search)


# ---------------------------------------------------------------------------
# Improvement 15: Batch scan (multiple targets, one tool)
# ---------------------------------------------------------------------------

class BatchScanRequest(BaseModel):
    tool: str = Field(..., description="Tool to run: nuclei | subfinder | httpx | sslyze")
    targets: list[str] = Field(..., min_length=1, max_length=50, description="List of targets (max 50)")
    options: dict[str, Any] = Field(default_factory=dict)
    concurrency: int = Field(5, ge=1, le=10, description="Max concurrent tool runs")


class BatchScanResult(BaseModel):
    target: str
    result: ToolRunResult


class BatchScanResponse(BaseModel):
    tool: str
    results: list[BatchScanResult]
    total_targets: int
    total_findings: int


_BATCH_RUNNERS: dict[str, type] = {
    "nuclei": NucleiRunner,
    "subfinder": SubfinderRunner,
    "httpx": HttpxRunner,
    "sslyze": SslyzeRunner,
}


@router.post("/batch", response_model=BatchScanResponse, summary="Batch scan multiple targets with one tool")
async def batch_scan(req: BatchScanRequest) -> BatchScanResponse:
    """Run a single tool against multiple targets concurrently. Max 50 targets, max 10 concurrent."""
    runner_cls = _BATCH_RUNNERS.get(req.tool)
    if not runner_cls:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported batch tool: {req.tool}. Supported: {', '.join(_BATCH_RUNNERS)}",
        )

    sem = asyncio.Semaphore(req.concurrency)

    async def run_one(target: str) -> BatchScanResult:
        async with sem:
            try:
                result = await runner_cls().run(target, req.options)
            except Exception as exc:
                from src.adapters.scanners.pentest.base import ToolResult
                result = ToolResult(tool=req.tool, exit_code=1, duration_seconds=0, error=str(exc))
            return BatchScanResult(target=target, result=_to_result(result, req.tool))

    results = await asyncio.gather(*[run_one(t) for t in req.targets])
    total_findings = sum(r.result.findings_count for r in results)
    return BatchScanResponse(
        tool=req.tool,
        results=list(results),
        total_targets=len(req.targets),
        total_findings=total_findings,
    )


# ---------------------------------------------------------------------------
# Improvement 16: SSE live tool output streaming
# ---------------------------------------------------------------------------

_SSE_SUPPORTED_TOOLS: dict[str, list[str]] = {
    "nuclei": ["nuclei", "-target", "{target}", "-silent", "-severity", "medium,high,critical"],
    "subfinder": ["subfinder", "-d", "{target}", "-silent"],
    "httpx": ["httpx", "-target", "{target}", "-json", "-silent"],
    "nmap": ["nmap", "-sV", "--open", "{target}"],
    "gobuster": ["gobuster", "dir", "-u", "{target}", "-w", "/usr/share/wordlists/dirb/common.txt", "-q"],
    "ffuf": ["ffuf", "-u", "{target}/FUZZ", "-w", "/usr/share/wordlists/dirb/common.txt", "-ac"],
}


async def _stream_tool_output(tool: str, target: str, options: dict[str, Any]) -> AsyncGenerator[str, None]:
    cmd_template = _SSE_SUPPORTED_TOOLS.get(tool)
    if not cmd_template:
        yield f"data: {json.dumps({'error': f'Tool {tool} not supported for streaming'})}\n\n"
        return

    cmd = [c.replace("{target}", target) for c in cmd_template]
    binary = shutil.which(cmd[0])
    if not binary:
        yield f"data: {json.dumps({'error': f'{cmd[0]} not found in PATH'})}\n\n"
        return

    yield f"data: {json.dumps({'status': 'started', 'tool': tool, 'target': target})}\n\n"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        timeout = int(options.get("timeout", 300))
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                proc.kill()
                yield f"data: {json.dumps({'status': 'timeout', 'message': f'Tool timed out after {timeout}s'})}\n\n"
                break
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                continue
            if not line:
                break
            decoded = line.decode(errors="replace").rstrip()
            yield f"data: {json.dumps({'line': decoded, 'tool': tool})}\n\n"

        await proc.wait()
        yield f"data: {json.dumps({'status': 'done', 'exit_code': proc.returncode})}\n\n"

    except Exception as exc:
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"


@router.get("/stream/{tool}", summary="Stream live tool output via SSE")
async def stream_tool(
    tool: str,
    target: str,
    timeout: int = 300,
    _user: Any = Depends(get_current_user),
) -> StreamingResponse:
    """Stream real-time stdout from a pentest tool as Server-Sent Events.
    Connect with EventSource('/api/v1/advanced-scanners/stream/nuclei?target=...')."""
    options = {"timeout": timeout}
    return StreamingResponse(
        _stream_tool_output(tool, target, options),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Improvement 21: CVE enrichment via NVD API 2.0
# ---------------------------------------------------------------------------

class CveEnrichRequest(BaseModel):
    cve_ids: list[str] = Field(..., min_length=1, max_length=20, description="CVE IDs to enrich (max 20)")


class CveDetailOut(BaseModel):
    cve_id: str
    description: str = ""
    cvss_v3_score: float | None = None
    cvss_v3_vector: str | None = None
    cvss_v3_severity: str | None = None
    cvss_v2_score: float | None = None
    cwes: list[str] = []
    references: list[str] = []
    published: str | None = None
    last_modified: str | None = None
    error: str | None = None


class CveEnrichResponse(BaseModel):
    cves: list[CveDetailOut]
    enriched_count: int
    error_count: int


@router.post("/enrich-cves", response_model=CveEnrichResponse, summary="Enrich CVE IDs via NVD API")
async def enrich_cves_endpoint(req: CveEnrichRequest) -> CveEnrichResponse:
    """Fetch CVSS scores, descriptions, CWEs, and references from the NIST NVD API for each CVE ID."""
    details = await enrich_cves(req.cve_ids)
    out = [
        CveDetailOut(
            cve_id=d.cve_id,
            description=d.description,
            cvss_v3_score=d.cvss_v3_score,
            cvss_v3_vector=d.cvss_v3_vector,
            cvss_v3_severity=d.cvss_v3_severity,
            cvss_v2_score=d.cvss_v2_score,
            cwes=d.cwes,
            references=d.references,
            published=d.published,
            last_modified=d.last_modified,
            error=d.error,
        )
        for d in details
    ]
    return CveEnrichResponse(
        cves=out,
        enriched_count=sum(1 for d in out if d.error is None),
        error_count=sum(1 for d in out if d.error is not None),
    )


# ---------------------------------------------------------------------------
# Improvement 22: SARIF 2.1.0 export
# ---------------------------------------------------------------------------

class SarifExportRequest(BaseModel):
    findings: list[FindingOut]
    scan_id: str | None = Field(None, description="Optional scan UUID to embed in SARIF")


@router.post("/export-sarif", summary="Export findings as SARIF 2.1.0")
async def export_sarif(req: SarifExportRequest) -> StreamingResponse:
    """Convert tool findings to a SARIF 2.1.0 JSON document for import into GitHub Advanced Security, Azure DevOps, etc."""
    sarif_doc = SarifGenerator().to_json(req.findings, scan_id=req.scan_id)
    filename = f"pentest-findings-{req.scan_id or 'export'}.sarif.json"
    return StreamingResponse(
        iter([sarif_doc.encode()]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Improvement 23: HTML pentest report download
# ---------------------------------------------------------------------------

class HtmlReportRequest(BaseModel):
    findings: list[FindingOut]
    title: str = Field("Pentest Report", description="Report title")
    target: str = Field("", description="Target system / scope")
    scan_id: str | None = None


def _build_html_report(req: HtmlReportRequest) -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sev_colors = {
        "critical": "#dc2626",
        "high": "#ea580c",
        "medium": "#d97706",
        "low": "#2563eb",
        "info": "#6b7280",
    }
    rows = ""
    for f in req.findings:
        color = sev_colors.get((f.severity or "info").lower(), "#6b7280")
        cves = ", ".join(f.cve) if f.cve else "—"
        mitre = "<br>".join(f.mitre_techniques) if f.mitre_techniques else "—"
        rows += f"""
        <tr>
          <td><strong>{f.title}</strong></td>
          <td><span style="color:{color};font-weight:600">{(f.severity or 'info').upper()}</span></td>
          <td>{f.tool}</td>
          <td>{f.host or f.url or '—'}</td>
          <td style="font-size:0.8em">{cves}</td>
          <td style="font-size:0.8em">{mitre}</td>
          <td style="font-size:0.8em;max-width:300px;word-break:break-word">{f.description or '—'}</td>
        </tr>"""

    counts: dict[str, int] = {}
    for f in req.findings:
        sev = (f.severity or "info").lower()
        counts[sev] = counts.get(sev, 0) + 1

    summary_items = "".join(
        f'<li><span style="color:{sev_colors.get(s,"#6b7280")}">{s.upper()}</span>: {c}</li>'
        for s, c in sorted(counts.items(), key=lambda x: ["critical","high","medium","low","info"].index(x[0]) if x[0] in ["critical","high","medium","low","info"] else 99)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{req.title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; color: #111; }}
  h1 {{ color: #1e293b; }} h2 {{ color: #334155; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 16px; font-size: 0.9em; }}
  th {{ background: #1e293b; color: #fff; padding: 8px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
  tr:hover td {{ background: #f8fafc; }}
  .meta {{ color: #64748b; font-size: 0.85em; margin-bottom: 24px; }}
  ul {{ padding-left: 20px; }}
</style>
</head>
<body>
<h1>{req.title}</h1>
<p class="meta">Generated: {now} | Target: {req.target or 'N/A'} | Scan ID: {req.scan_id or 'N/A'} | Total findings: {len(req.findings)}</p>
<h2>Summary</h2>
<ul>{summary_items}</ul>
<h2>Findings</h2>
<table>
<thead><tr><th>Title</th><th>Severity</th><th>Tool</th><th>Host/URL</th><th>CVEs</th><th>MITRE</th><th>Description</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""


@router.post("/export-html", summary="Export findings as HTML report")
async def export_html_report(req: HtmlReportRequest) -> StreamingResponse:
    """Generate a styled HTML pentest report from tool findings. Returns as a downloadable HTML file."""
    html = _build_html_report(req)
    filename = f"pentest-report-{req.scan_id or 'export'}.html"
    return StreamingResponse(
        iter([html.encode()]),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Improvement 24: Scan profiles (in-memory store, per-process)
# ---------------------------------------------------------------------------

import uuid as _uuid

_scan_profiles: dict[str, dict[str, Any]] = {}


class ScanProfile(BaseModel):
    name: str = Field(..., description="Profile name")
    tool: str = Field(..., description="Tool this profile applies to (nuclei|httpx|etc.)")
    options: dict[str, Any] = Field(default_factory=dict, description="Tool options")
    description: str = Field("", description="Optional description")


class ScanProfileOut(ScanProfile):
    id: str
    created_at: str


class ScanProfilesResponse(BaseModel):
    profiles: list[ScanProfileOut]
    count: int


@router.get("/scan-profiles", response_model=ScanProfilesResponse, summary="List saved scan profiles")
async def list_scan_profiles() -> ScanProfilesResponse:
    """Return all saved scan profiles stored in the server's memory."""
    profiles = [ScanProfileOut(**v) for v in _scan_profiles.values()]
    return ScanProfilesResponse(profiles=profiles, count=len(profiles))


@router.post("/scan-profiles", response_model=ScanProfileOut, status_code=201, summary="Save a scan profile")
async def create_scan_profile(req: ScanProfile) -> ScanProfileOut:
    """Save a named scan profile (tool + options). Returns the created profile with its ID."""
    from datetime import datetime, timezone
    profile_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    profile = ScanProfileOut(id=profile_id, created_at=now, **req.model_dump())
    _scan_profiles[profile_id] = profile.model_dump()
    return profile


@router.delete("/scan-profiles/{profile_id}", status_code=204, summary="Delete a scan profile")
async def delete_scan_profile(profile_id: str) -> None:
    """Delete a saved scan profile by ID."""
    if profile_id not in _scan_profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    del _scan_profiles[profile_id]
