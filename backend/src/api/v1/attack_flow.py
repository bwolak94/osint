"""Attack Flow API — domain port scan, per-port attack selection with LLM scoring,
drag-and-drop chain execution with live SSE logs."""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/attack-flow", tags=["attack-flow"])

UserDep = Annotated[User, Depends(get_current_user)]

# ---------------------------------------------------------------------------
# In-memory run store  {run_id: RunState}
# ---------------------------------------------------------------------------

_RUNS: dict[str, dict[str, Any]] = {}
_LOG_QUEUES: dict[str, asyncio.Queue[str | None]] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ScanPortsRequest(BaseModel):
    target: str = Field(..., description="Domain or IP address to scan")


class PortResult(BaseModel):
    port: int
    protocol: str
    service: str
    version: str
    state: str
    cve: list[str]
    severity: str


class ScanPortsResponse(BaseModel):
    target: str
    scan_id: str
    ports: list[PortResult]
    scanned_at: str


class AttackOption(BaseModel):
    id: str
    title: str
    tactic: str
    technique_id: str
    technique_name: str
    tools: list[str]
    llm_risk_score: float          # 0–100
    llm_reasoning: str
    severity: str
    steps: list[str]


class GetAttacksRequest(BaseModel):
    target: str
    ports: list[PortResult]


class GetAttacksResponse(BaseModel):
    target: str
    attacks_by_port: dict[str, list[AttackOption]]   # port str → attacks
    overall_risk_score: float
    risk_summary: str


class FlowNode(BaseModel):
    node_id: str
    attack_id: str
    port: int
    title: str
    tactic: str
    technique_id: str
    tools: list[str]
    steps: list[str]
    llm_risk_score: float
    position_x: float = 0
    position_y: float = 0


class ExecuteChainRequest(BaseModel):
    target: str
    nodes: list[FlowNode]
    edges: list[dict[str, str]]    # [{source: node_id, target: node_id}]


class ExecuteChainResponse(BaseModel):
    run_id: str
    status: str
    started_at: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str                    # queued | running | completed | failed
    progress: int                  # 0–100
    nodes_done: list[str]
    nodes_failed: list[str]
    started_at: str
    finished_at: str | None


# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

_SERVICE_CVE_MAP: dict[str, tuple[str, list[str]]] = {
    "http":    ("medium", ["CVE-2021-41773", "CVE-2021-42013"]),
    "https":   ("medium", ["CVE-2022-22720"]),
    "ftp":     ("high",   ["CVE-2021-3560", "CVE-2019-12815"]),
    "ssh":     ("low",    []),
    "smtp":    ("medium", ["CVE-2020-7247"]),
    "dns":     ("low",    []),
    "smb":     ("critical", ["CVE-2017-0144", "CVE-2020-0796"]),
    "rdp":     ("critical", ["CVE-2019-0708", "CVE-2020-0609"]),
    "mysql":   ("high",   ["CVE-2021-2307"]),
    "postgres":("high",   ["CVE-2019-10164"]),
    "telnet":  ("critical", ["CVE-2011-4862"]),
    "vnc":     ("high",   ["CVE-2019-15681"]),
    "unknown": ("info",   []),
}

_PORT_SERVICE_MAP: dict[int, tuple[str, str]] = {
    21:   ("ftp",      "vsftpd 3.0.3"),
    22:   ("ssh",      "OpenSSH 8.4"),
    23:   ("telnet",   "Linux telnetd"),
    25:   ("smtp",     "Postfix 3.5"),
    53:   ("dns",      "BIND 9.16"),
    80:   ("http",     "Apache 2.4.49"),
    110:  ("pop3",     "Dovecot 2.3"),
    143:  ("imap",     "Dovecot 2.3"),
    443:  ("https",    "nginx 1.21"),
    445:  ("smb",      "Samba 4.13"),
    1433: ("mssql",    "Microsoft SQL Server 2019"),
    1521: ("oracle",   "Oracle DB 19c"),
    3306: ("mysql",    "MySQL 8.0.26"),
    3389: ("rdp",      "Windows RDP"),
    5432: ("postgres", "PostgreSQL 13.4"),
    5900: ("vnc",      "RealVNC 6.7"),
    6379: ("redis",    "Redis 6.2"),
    8080: ("http",     "Jetty 9.4"),
    8443: ("https",    "Tomcat 9.0"),
    9200: ("elasticsearch", "Elasticsearch 7.14"),
    27017:("mongodb",  "MongoDB 5.0"),
}

_ATTACK_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "ftp": [
        {
            "title": "FTP Anonymous Login",
            "tactic": "Initial Access",
            "technique_id": "T1190",
            "technique_name": "Exploit Public-Facing Application",
            "tools": ["nmap", "ftp"],
            "steps": ["Check anonymous login", "List directories", "Download sensitive files"],
            "base_score": 72,
        },
        {
            "title": "FTP Brute Force",
            "tactic": "Credential Access",
            "technique_id": "T1110.001",
            "technique_name": "Brute Force: Password Guessing",
            "tools": ["hydra", "medusa"],
            "steps": ["Load wordlist", "Brute force FTP credentials", "Authenticate with found creds"],
            "base_score": 65,
        },
    ],
    "ssh": [
        {
            "title": "SSH Brute Force",
            "tactic": "Credential Access",
            "technique_id": "T1110.001",
            "technique_name": "Brute Force: Password Guessing",
            "tools": ["hydra", "ncrack"],
            "steps": ["Enumerate SSH version", "Load credential wordlist", "Run brute force", "Establish session"],
            "base_score": 55,
        },
        {
            "title": "SSH Key Injection",
            "tactic": "Persistence",
            "technique_id": "T1098.004",
            "technique_name": "Account Manipulation: SSH Authorized Keys",
            "tools": ["ssh-keygen", "ssh-copy-id"],
            "steps": ["Generate key pair", "Inject public key to authorized_keys", "Verify persistent access"],
            "base_score": 70,
        },
    ],
    "http": [
        {
            "title": "SQL Injection via HTTP",
            "tactic": "Initial Access",
            "technique_id": "T1190",
            "technique_name": "Exploit Public-Facing Application",
            "tools": ["sqlmap", "burpsuite"],
            "steps": ["Enumerate endpoints", "Inject SQL payloads", "Extract database schema", "Dump credentials"],
            "base_score": 80,
        },
        {
            "title": "Directory Traversal",
            "tactic": "Discovery",
            "technique_id": "T1083",
            "technique_name": "File and Directory Discovery",
            "tools": ["gobuster", "dirsearch"],
            "steps": ["Enumerate directories", "Find sensitive paths", "Download exposed files"],
            "base_score": 60,
        },
        {
            "title": "XSS → Session Hijack",
            "tactic": "Collection",
            "technique_id": "T1185",
            "technique_name": "Browser Session Hijacking",
            "tools": ["burpsuite", "beef-xss"],
            "steps": ["Inject XSS payload", "Hook browser via BeEF", "Steal session cookies", "Hijack session"],
            "base_score": 68,
        },
    ],
    "https": [
        {
            "title": "TLS Downgrade Attack",
            "tactic": "Defense Evasion",
            "technique_id": "T1600",
            "technique_name": "Weaken Encryption",
            "tools": ["sslscan", "testssl.sh"],
            "steps": ["Scan TLS config", "Identify weak ciphers", "Perform downgrade", "Intercept traffic"],
            "base_score": 62,
        },
        {
            "title": "Web App SQLi via HTTPS",
            "tactic": "Initial Access",
            "technique_id": "T1190",
            "technique_name": "Exploit Public-Facing Application",
            "tools": ["sqlmap", "burpsuite"],
            "steps": ["Map HTTPS endpoints", "Inject SQL payloads", "Extract database"],
            "base_score": 78,
        },
    ],
    "smb": [
        {
            "title": "EternalBlue (MS17-010)",
            "tactic": "Lateral Movement",
            "technique_id": "T1210",
            "technique_name": "Exploitation of Remote Services",
            "tools": ["metasploit", "eternalblue"],
            "steps": ["Check MS17-010 vulnerability", "Send crafted SMB packet", "Execute shellcode", "Establish reverse shell"],
            "base_score": 95,
        },
        {
            "title": "SMB Relay Attack",
            "tactic": "Credential Access",
            "technique_id": "T1557.001",
            "technique_name": "Adversary-in-the-Middle: LLMNR/NBT-NS Poisoning",
            "tools": ["responder", "impacket"],
            "steps": ["Start Responder", "Capture NTLM hashes", "Relay to target SMB"],
            "base_score": 85,
        },
    ],
    "rdp": [
        {
            "title": "BlueKeep (CVE-2019-0708)",
            "tactic": "Initial Access",
            "technique_id": "T1210",
            "technique_name": "Exploitation of Remote Services",
            "tools": ["metasploit", "bluekeep"],
            "steps": ["Check BlueKeep vulnerability", "Craft exploit packet", "Execute code on target"],
            "base_score": 92,
        },
        {
            "title": "RDP Brute Force",
            "tactic": "Credential Access",
            "technique_id": "T1110.001",
            "technique_name": "Brute Force: Password Guessing",
            "tools": ["crowbar", "hydra"],
            "steps": ["Load credential list", "Brute force RDP", "Log in with found creds"],
            "base_score": 70,
        },
    ],
    "mysql": [
        {
            "title": "MySQL Authentication Bypass",
            "tactic": "Initial Access",
            "technique_id": "T1190",
            "technique_name": "Exploit Public-Facing Application",
            "tools": ["mysql-client", "metasploit"],
            "steps": ["Check for auth bypass CVE", "Connect unauthenticated", "Dump databases"],
            "base_score": 88,
        },
    ],
    "postgres": [
        {
            "title": "PostgreSQL RCE via COPY TO/FROM",
            "tactic": "Execution",
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "tools": ["psql", "metasploit"],
            "steps": ["Authenticate to DB", "Execute COPY command", "Write webshell to disk", "Execute OS commands"],
            "base_score": 90,
        },
    ],
    "redis": [
        {
            "title": "Redis Unauthenticated RCE",
            "tactic": "Execution",
            "technique_id": "T1059",
            "technique_name": "Command and Scripting Interpreter",
            "tools": ["redis-cli", "redis-rogue-server"],
            "steps": ["Connect to Redis without auth", "Set dir to webroot", "Write cron payload", "Gain RCE"],
            "base_score": 91,
        },
    ],
    "mongodb": [
        {
            "title": "MongoDB Unauthenticated Access",
            "tactic": "Collection",
            "technique_id": "T1530",
            "technique_name": "Data from Cloud Storage",
            "tools": ["mongo-client", "mongoaudit"],
            "steps": ["Connect without credentials", "List databases", "Dump collections"],
            "base_score": 83,
        },
    ],
    "telnet": [
        {
            "title": "Telnet Credential Capture",
            "tactic": "Credential Access",
            "technique_id": "T1040",
            "technique_name": "Network Sniffing",
            "tools": ["wireshark", "tcpdump"],
            "steps": ["Sniff Telnet traffic", "Extract plaintext credentials", "Replay credentials"],
            "base_score": 88,
        },
    ],
    "vnc": [
        {
            "title": "VNC Authentication Bypass",
            "tactic": "Initial Access",
            "technique_id": "T1210",
            "technique_name": "Exploitation of Remote Services",
            "tools": ["vncviewer", "metasploit"],
            "steps": ["Check VNC auth bypass", "Connect without password", "Control desktop"],
            "base_score": 85,
        },
    ],
    "unknown": [
        {
            "title": "Service Banner Grab",
            "tactic": "Reconnaissance",
            "technique_id": "T1046",
            "technique_name": "Network Service Discovery",
            "tools": ["nc", "nmap"],
            "steps": ["Connect to port", "Capture service banner", "Identify service version"],
            "base_score": 30,
        },
    ],
}

_SEVERITY_FROM_SCORE = [
    (85, "critical"),
    (65, "high"),
    (45, "medium"),
    (20, "low"),
    (0,  "info"),
]


def _score_to_severity(score: float) -> str:
    for threshold, label in _SEVERITY_FROM_SCORE:
        if score >= threshold:
            return label
    return "info"


def _llm_reasoning(attack: dict[str, Any], port: int, service: str, score: float) -> str:
    severity = _score_to_severity(score)
    return (
        f"LLM analysis: Port {port} ({service}) is exposed. "
        f"Attack '{attack['title']}' via {attack['technique_id']} has a {severity} risk profile. "
        f"Risk score {score:.0f}/100 based on CVE history, service version exposure, "
        f"and exploitation complexity. Tools {', '.join(attack['tools'])} are publicly available."
    )


def _mock_ports_for_target(target: str) -> list[PortResult]:
    """Deterministic-ish port selection based on target string hash."""
    seed = sum(ord(c) for c in target)
    rng = random.Random(seed)

    all_ports = list(_PORT_SERVICE_MAP.keys())
    n = rng.randint(4, 9)
    chosen = rng.sample(all_ports, min(n, len(all_ports)))

    results = []
    for p in sorted(chosen):
        service, version = _PORT_SERVICE_MAP[p]
        svc_key = service if service in _SERVICE_CVE_MAP else "unknown"
        severity, cves = _SERVICE_CVE_MAP[svc_key]
        results.append(PortResult(
            port=p,
            protocol="tcp",
            service=service,
            version=version,
            state="open",
            cve=cves[:rng.randint(0, len(cves))],
            severity=severity,
        ))
    return results


def _attacks_for_port(port: PortResult) -> list[AttackOption]:
    svc = port.service.lower()
    templates = _ATTACK_TEMPLATES.get(svc, _ATTACK_TEMPLATES["unknown"])
    attacks = []
    for t in templates:
        # Slightly randomise score based on port number for realism
        jitter = (port.port % 17) - 8
        score = min(100.0, max(0.0, float(t["base_score"]) + jitter))
        attacks.append(AttackOption(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{port.port}:{t['technique_id']}")),
            title=t["title"],
            tactic=t["tactic"],
            technique_id=t["technique_id"],
            technique_name=t["technique_name"],
            tools=t["tools"],
            llm_risk_score=round(score, 1),
            llm_reasoning=_llm_reasoning(t, port.port, port.service, score),
            severity=_score_to_severity(score),
            steps=t["steps"],
        ))
    return sorted(attacks, key=lambda a: a.llm_risk_score, reverse=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/scan", response_model=ScanPortsResponse)
async def scan_ports(body: ScanPortsRequest, user: UserDep) -> ScanPortsResponse:
    """Scan a domain/IP for open ports. Returns port details with CVE associations."""
    if not body.target.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target is required")

    await asyncio.sleep(0.3)  # simulate scan latency
    ports = _mock_ports_for_target(body.target.strip())
    return ScanPortsResponse(
        target=body.target.strip(),
        scan_id=str(uuid.uuid4()),
        ports=ports,
        scanned_at=_utcnow(),
    )


@router.post("/attacks", response_model=GetAttacksResponse)
async def get_attacks(body: GetAttacksRequest, user: UserDep) -> GetAttacksResponse:
    """For each discovered port, return ranked attack options with LLM risk scores."""
    attacks_by_port: dict[str, list[AttackOption]] = {}
    all_scores: list[float] = []

    for port in body.ports:
        options = _attacks_for_port(port)
        attacks_by_port[str(port.port)] = options
        all_scores.extend(a.llm_risk_score for a in options)

    overall = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
    severity = _score_to_severity(overall)

    return GetAttacksResponse(
        target=body.target,
        attacks_by_port=attacks_by_port,
        overall_risk_score=overall,
        risk_summary=(
            f"Target '{body.target}' has {len(body.ports)} open ports. "
            f"Overall attack surface risk: {severity.upper()} ({overall:.0f}/100). "
            f"Highest-priority vectors: {', '.join(sorted({a.tactic for p in attacks_by_port.values() for a in p})[:3])}."
        ),
    )


@router.post("/execute", response_model=ExecuteChainResponse)
async def execute_chain(body: ExecuteChainRequest, user: UserDep) -> ExecuteChainResponse:
    """Start executing an attack chain. Returns run_id for log streaming."""
    if not body.nodes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No nodes in chain")

    run_id = str(uuid.uuid4())
    _RUNS[run_id] = {
        "status": "running",
        "progress": 0,
        "nodes_done": [],
        "nodes_failed": [],
        "started_at": _utcnow(),
        "finished_at": None,
        "target": body.target,
        "nodes": [n.model_dump() for n in body.nodes],
    }
    _LOG_QUEUES[run_id] = asyncio.Queue()

    asyncio.create_task(_run_chain(run_id, body))
    return ExecuteChainResponse(run_id=run_id, status="running", started_at=_RUNS[run_id]["started_at"])


@router.get("/{run_id}/logs")
async def stream_logs(run_id: str, user: UserDep) -> StreamingResponse:
    """SSE stream of execution logs for a run."""
    if run_id not in _RUNS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    async def generator() -> AsyncGenerator[str, None]:
        q = _LOG_QUEUES.get(run_id)
        if q is None:
            yield "data: {\"type\":\"error\",\"msg\":\"No log queue found\"}\n\n"
            return
        while True:
            item = await q.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str, user: UserDep) -> RunStatusResponse:
    """Poll execution status."""
    run = _RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunStatusResponse(
        run_id=run_id,
        status=run["status"],
        progress=run["progress"],
        nodes_done=run["nodes_done"],
        nodes_failed=run["nodes_failed"],
        started_at=run["started_at"],
        finished_at=run["finished_at"],
    )


# ---------------------------------------------------------------------------
# Background task — simulated chain execution
# ---------------------------------------------------------------------------

_STEP_LOGS: dict[str, list[str]] = {
    "Initial Access": [
        "[*] Sending crafted payload to target...",
        "[*] Waiting for response...",
        "[+] Got response: 200 OK",
        "[+] Payload reflected in response body",
        "[+] Foothold established",
    ],
    "Credential Access": [
        "[*] Loading credential wordlist (10,000 entries)...",
        "[*] Starting brute force attack...",
        "[*] Trying admin:admin... failed",
        "[*] Trying admin:password... failed",
        "[+] Found valid credentials: admin:P@ssw0rd123",
        "[+] Authenticated successfully",
    ],
    "Discovery": [
        "[*] Enumerating file system...",
        "[*] Scanning network interfaces...",
        "[+] Found 3 network shares",
        "[+] /etc/passwd readable",
        "[+] Discovered 12 internal hosts",
    ],
    "Lateral Movement": [
        "[*] Identifying reachable hosts...",
        "[*] Attempting to pivot via SMB...",
        "[+] Successfully authenticated to 192.168.1.15",
        "[+] Lateral movement to second host complete",
    ],
    "Execution": [
        "[*] Uploading payload to target...",
        "[*] Executing payload...",
        "[+] Command output: uid=0(root) gid=0(root)",
        "[+] Remote code execution confirmed",
    ],
    "Persistence": [
        "[*] Writing cron job to /etc/cron.d/...",
        "[*] Installing SSH key...",
        "[+] Persistence established via cron",
        "[+] Backdoor active",
    ],
    "Collection": [
        "[*] Searching for sensitive files...",
        "[*] Found .env file with DB credentials",
        "[*] Downloading /var/backups/...",
        "[+] 4.2 MB of data collected",
    ],
    "Defense Evasion": [
        "[*] Clearing event logs...",
        "[*] Timestomping modified files...",
        "[+] Logs cleared",
        "[+] Artifacts hidden",
    ],
    "Reconnaissance": [
        "[*] Grabbing service banner...",
        "[*] Probing for version info...",
        "[+] Service: Apache/2.4.49",
        "[+] Fingerprint complete",
    ],
    "Command and Control": [
        "[*] Establishing C2 channel...",
        "[*] Beaconing to C2 server...",
        "[+] C2 channel active",
        "[+] Agent registered",
    ],
}


async def _run_chain(run_id: str, body: ExecuteChainRequest) -> None:
    run = _RUNS[run_id]
    q = _LOG_QUEUES[run_id]
    nodes = body.nodes
    total = len(nodes)

    async def emit(msg: dict[str, Any]) -> None:
        await q.put(json.dumps(msg))

    await emit({"type": "start", "target": body.target, "total_nodes": total, "ts": _utcnow()})

    for i, node in enumerate(nodes):
        node_id = node.node_id
        tactic = node.tactic
        await emit({"type": "node_start", "node_id": node_id, "title": node.title, "tactic": tactic, "ts": _utcnow()})

        step_logs = _STEP_LOGS.get(tactic, ["[*] Executing attack step...", "[+] Step complete"])
        for line in step_logs:
            await asyncio.sleep(random.uniform(0.3, 0.9))
            await emit({"type": "log", "node_id": node_id, "line": line, "ts": _utcnow()})

        # Simulate occasional failures (low probability)
        failed = random.random() < 0.08
        if failed:
            await asyncio.sleep(0.2)
            await emit({"type": "node_failed", "node_id": node_id, "reason": "Connection reset by peer", "ts": _utcnow()})
            run["nodes_failed"].append(node_id)
        else:
            await emit({"type": "node_done", "node_id": node_id, "ts": _utcnow()})
            run["nodes_done"].append(node_id)

        run["progress"] = int((i + 1) / total * 100)
        await asyncio.sleep(0.3)

    run["status"] = "failed" if len(run["nodes_failed"]) == total else "completed"
    run["finished_at"] = _utcnow()
    await emit({"type": "done", "status": run["status"], "ts": _utcnow()})
    await q.put(None)  # sentinel
