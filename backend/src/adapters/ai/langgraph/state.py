"""PentestState — shared state passed between LangGraph agent nodes."""

from __future__ import annotations

from typing import Any, TypedDict


class PortInfo(TypedDict):
    port: int
    protocol: str        # tcp / udp
    state: str           # open / filtered
    service: str
    version: str
    cpe: str


class VulnHint(TypedDict):
    cve: str
    cvss: float
    epss: float
    kev: bool
    description: str
    affected_service: str


class AttackScenario(TypedDict):
    id: str
    title: str
    tactic: str               # MITRE tactic
    technique_id: str         # T1234
    technique_name: str
    tools: list[str]
    preconditions: list[str]
    severity: str
    likelihood: str
    steps: list[str]


class PentestState(TypedDict, total=False):
    """Mutable shared state that flows through the multi-agent graph."""

    # Input (set at graph entry)
    scan_id: str
    engagement_id: str
    target: str
    profile: str               # quick / standard / deep / custom
    selected_modules: list[str]

    # Recon agent output
    open_ports: list[PortInfo]
    subdomains: list[str]
    technologies: list[str]
    web_paths: list[str]
    tls_issues: list[str]
    recon_summary: str

    # Vuln research agent output (RAG + EPSS enrichment)
    vuln_hints: list[VulnHint]
    rag_chunks: list[dict[str, Any]]
    vuln_summary: str

    # HITL gate
    hitl_required: bool
    hitl_request_id: str | None
    hitl_approved: bool | None   # None = pending, True = approved, False = rejected

    # Attack planner output (post-HITL)
    attack_scenarios: list[AttackScenario]
    ptt: dict[str, Any]          # Pentesting Task Tree — persisted to scan.ptt JSONB

    # Reporter output
    exec_summary_en: str
    exec_summary_pl: str
    risk_level: str              # critical / high / medium / low / info
    key_findings: list[str]
    recommended_actions: list[str]

    # Orchestration bookkeeping
    current_agent: str
    error: str | None
    completed: bool
