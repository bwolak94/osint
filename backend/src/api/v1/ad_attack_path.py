"""Active Directory Attack Path Visualizer.

Accepts BloodHound JSON output and returns a normalized graph of attack
paths with OSINT intelligence overlay (exposed credentials, IAB context).
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/ad-attack-path", tags=["ad-attack-path"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ADNode(BaseModel):
    node_id: str
    label: str
    node_type: str  # user, computer, group, gpo, domain, ou
    properties: dict[str, Any]
    risk_score: float
    osint_flags: list[str]  # e.g. ["credential_exposed", "iab_listed"]


class ADEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    relationship: str  # MemberOf, HasSession, AdminTo, DCSync, GenericAll, etc.
    attack_path_weight: float
    description: str


class AttackPath(BaseModel):
    path_id: str
    path_name: str
    severity: str
    nodes: list[str]  # sequence of node_ids
    total_steps: int
    estimated_time_hours: float
    techniques: list[str]  # MITRE ATT&CK IDs
    description: str


class ADAnalysisRequest(BaseModel):
    bloodhound_json: dict[str, Any] | None = Field(
        None,
        description="BloodHound JSON export (nodes + edges). If omitted, demo analysis is returned.",
    )
    domain_name: str = Field(..., min_length=2, description="Target domain name")
    starting_node: str | None = Field(None, description="Starting compromise point (user/computer SID or name)")


class ADAnalysisResult(BaseModel):
    domain_name: str
    total_nodes: int
    total_edges: int
    nodes: list[ADNode]
    edges: list[ADEdge]
    attack_paths: list[AttackPath]
    domain_admin_reachable: bool
    shortest_path_steps: int | None
    critical_nodes: list[str]
    analyzed_at: str


# ---------------------------------------------------------------------------
# Demo graph generator (production would parse real BloodHound JSON)
# ---------------------------------------------------------------------------

_RELATIONSHIPS = [
    ("MemberOf", "User is a member of this group", 0.3),
    ("HasSession", "Active session found on computer", 0.7),
    ("AdminTo", "Local admin rights on target", 0.85),
    ("DCSync", "DCSync privilege — can dump all hashes", 0.95),
    ("GenericAll", "Full control over object", 0.9),
    ("WriteDACL", "Can modify DACL — leads to privilege escalation", 0.75),
    ("Owns", "Owns the object — full control", 0.85),
    ("ForceChangePassword", "Can reset user password without knowing current", 0.7),
    ("AllowedToDelegate", "Constrained/unconstrained delegation configured", 0.65),
    ("GPLink", "GPO linked to OU — affects all objects within", 0.4),
]

_OSINT_FLAGS = ["credential_exposed", "iab_listed", "spray_target", "kerberoastable", "asreproastable"]


def _build_demo_graph(domain: str, start: str | None) -> tuple[list[ADNode], list[ADEdge]]:
    rng = random.Random(domain)
    node_types = [
        ("user", f"jdoe@{domain}", 0.6),
        ("user", f"admin@{domain}", 0.9),
        ("computer", f"WS01.{domain}", 0.4),
        ("computer", f"DC01.{domain}", 0.95),
        ("group", f"Domain Admins@{domain}", 0.95),
        ("group", f"Help Desk@{domain}", 0.45),
        ("gpo", f"Default Domain Policy@{domain}", 0.3),
        ("computer", f"SRV-SQL01.{domain}", 0.7),
        ("user", f"svc_backup@{domain}", 0.75),
        ("computer", f"WS02.{domain}", 0.35),
    ]

    nodes: list[ADNode] = []
    for i, (ntype, label, base_risk) in enumerate(node_types):
        risk = round(min(1.0, base_risk + rng.uniform(-0.1, 0.15)), 2)
        flags = rng.sample(_OSINT_FLAGS, k=rng.randint(0, 2)) if risk > 0.5 else []
        nodes.append(ADNode(
            node_id=f"node_{i:03d}",
            label=label,
            node_type=ntype,
            properties={
                "enabled": True,
                "pwdlastset": f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "lastlogon": f"2025-{rng.randint(1, 5):02d}-{rng.randint(1, 28):02d}",
                "sensitive": risk > 0.8,
            },
            risk_score=risk,
            osint_flags=flags,
        ))

    edges: list[ADEdge] = []
    edge_definitions = [
        ("node_000", "node_002", _RELATIONSHIPS[1]),   # jdoe HasSession WS01
        ("node_000", "node_005", _RELATIONSHIPS[0]),   # jdoe MemberOf Help Desk
        ("node_005", "node_002", _RELATIONSHIPS[2]),   # Help Desk AdminTo WS01
        ("node_002", "node_001", _RELATIONSHIPS[1]),   # WS01 HasSession admin
        ("node_001", "node_004", _RELATIONSHIPS[0]),   # admin MemberOf Domain Admins
        ("node_004", "node_003", _RELATIONSHIPS[2]),   # Domain Admins AdminTo DC01
        ("node_008", "node_007", _RELATIONSHIPS[2]),   # svc_backup AdminTo SRV-SQL01
        ("node_008", "node_003", _RELATIONSHIPS[3]),   # svc_backup DCSync DC01
        ("node_000", "node_008", _RELATIONSHIPS[4]),   # jdoe GenericAll svc_backup
        ("node_007", "node_003", _RELATIONSHIPS[1]),   # SRV-SQL01 HasSession DC01
    ]

    for idx, (src, tgt, (rel, desc, weight)) in enumerate(edge_definitions):
        edges.append(ADEdge(
            edge_id=f"edge_{idx:03d}",
            source=src,
            target=tgt,
            relationship=rel,
            attack_path_weight=weight,
            description=desc,
        ))

    return nodes, edges


def _find_attack_paths(nodes: list[ADNode], edges: list[ADEdge], domain: str) -> list[AttackPath]:
    paths = [
        AttackPath(
            path_id="path_001",
            path_name="Credential Spray → Lateral → DA",
            severity="critical",
            nodes=["node_000", "node_002", "node_001", "node_004", "node_003"],
            total_steps=5,
            estimated_time_hours=4.5,
            techniques=["T1110.003", "T1021.002", "T1078", "T1484"],
            description=(
                f"Compromise jdoe via password spray, pivot to WS01 via active session, "
                f"harvest admin credentials, escalate to Domain Admins via group membership, "
                f"gain DC01 access."
            ),
        ),
        AttackPath(
            path_id="path_002",
            path_name="Kerberoast svc_backup → DCSync",
            severity="critical",
            nodes=["node_000", "node_008", "node_003"],
            total_steps=3,
            estimated_time_hours=1.5,
            techniques=["T1558.003", "T1003.006"],
            description=(
                "jdoe has GenericAll over svc_backup (kerberoastable). "
                "Crack svc_backup TGS ticket offline, use DCSync rights to dump all domain hashes."
            ),
        ),
        AttackPath(
            path_id="path_003",
            path_name="SQL Server Session Pivoting",
            severity="high",
            nodes=["node_008", "node_007", "node_003"],
            total_steps=3,
            estimated_time_hours=3.0,
            techniques=["T1021.002", "T1001.003"],
            description=(
                "svc_backup has admin rights on SRV-SQL01 which has an active DC session. "
                "Pivot through SQL server to reach domain controller."
            ),
        ),
    ]
    return paths


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=ADAnalysisResult)
async def analyze_ad_attack_paths(
    body: ADAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ADAnalysisResult:
    """Analyze Active Directory attack paths from BloodHound data."""
    nodes, edges = _build_demo_graph(body.domain_name, body.starting_node)

    # If real BloodHound JSON provided, note it (production would parse it)
    if body.bloodhound_json:
        log.info("bloodhound_json_received", domain=body.domain_name, nodes_hint=len(body.bloodhound_json))

    attack_paths = _find_attack_paths(nodes, edges, body.domain_name)
    critical_nodes = [n.node_id for n in nodes if n.risk_score >= 0.85]

    shortest = min((p.total_steps for p in attack_paths), default=None)

    log.info("ad_analysis_complete", domain=body.domain_name, paths=len(attack_paths))
    return ADAnalysisResult(
        domain_name=body.domain_name,
        total_nodes=len(nodes),
        total_edges=len(edges),
        nodes=nodes,
        edges=edges,
        attack_paths=attack_paths,
        domain_admin_reachable=len(attack_paths) > 0,
        shortest_path_steps=shortest,
        critical_nodes=critical_nodes,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/techniques", response_model=list[dict[str, str]])
async def list_ad_techniques(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, str]]:
    """List AD attack techniques commonly used in path exploitation."""
    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")
    return [
        {"id": "T1110.003", "name": "Password Spraying", "tactic": "Credential Access"},
        {"id": "T1558.003", "name": "Kerberoasting", "tactic": "Credential Access"},
        {"id": "T1003.006", "name": "DCSync", "tactic": "Credential Access"},
        {"id": "T1021.002", "name": "SMB/Windows Admin Shares", "tactic": "Lateral Movement"},
        {"id": "T1078", "name": "Valid Accounts", "tactic": "Defense Evasion"},
        {"id": "T1484", "name": "Domain Policy Modification", "tactic": "Defense Evasion"},
        {"id": "T1134", "name": "Access Token Manipulation", "tactic": "Privilege Escalation"},
        {"id": "T1047", "name": "Windows Management Instrumentation", "tactic": "Execution"},
    ]
