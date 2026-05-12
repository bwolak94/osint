"""Agent nodes for the PentAI LangGraph state machine.

Each agent is an async function that accepts a PentestState dict, performs its
work, and returns a *partial* state update dict.  The caller (graph.py) merges
the update into the running state.

Agents:
  recon_agent          — aggregate recon data from existing scan steps / tools
  vuln_research_agent  — RAG search + EPSS enrichment for discovered services
  attack_planner_agent — build Pentesting Task Tree (requires HITL approval)
  reporter_agent       — generate bilingual executive summary
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import structlog

from src.config import get_settings

from .state import AttackScenario, PentestState, PortInfo, VulnHint

log = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _ollama_chat(model: str, system: str, user: str, scan_id: str | None = None) -> str:
    """Thin Ollama chat wrapper — streams tokens and publishes to Redis if scan_id given."""
    settings = get_settings()
    url = f"{settings.ollama_host}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "options": {
            "num_predict": 512,   # cap output tokens → faster, fewer timeouts
            "num_ctx": 2048,      # smaller context window → less memory pressure
        },
    }

    redis_client = None
    if scan_id:
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            redis_client = None

    full_content = ""
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_content += token
                            if redis_client:
                                try:
                                    await redis_client.publish(
                                        f"pentest:ai:{scan_id}:stream",
                                        json.dumps({"type": "token", "token": token}),
                                    )
                                except Exception:
                                    pass
                        if chunk.get("done"):
                            break
                    except Exception:
                        continue
    except Exception as exc:
        log.warning("ollama_chat_failed", model=model, error=str(exc))
    finally:
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception:
                pass

    return full_content or "{}"


async def _emit(scan_id: str | None, event_type: str, **kwargs: object) -> None:
    """Publish a structured event to the Redis stream channel for this scan."""
    if not scan_id:
        return
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        payload = json.dumps({"type": event_type, **{k: v for k, v in kwargs.items()}})
        await r.publish(f"pentest:ai:{scan_id}:stream", payload)
        await r.aclose()
    except Exception:
        pass


def _extract_json(text: str) -> str:
    """Extract JSON from LLM output that may be wrapped in markdown fences."""
    import re
    # Try ```json ... ``` block first
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # Try first {...} block
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Agent nodes
# ─────────────────────────────────────────────────────────────────────────────

async def recon_agent(state: PentestState, db: Any) -> dict[str, Any]:
    """Aggregate recon data from DB scan steps into structured state."""
    await _emit(state.get("scan_id"), "agent_start", agent="recon", label="Recon — aggregating scan data")
    from sqlalchemy import select
    from src.adapters.db.pentest_models import PentestFindingModel, ScanStepModel

    scan_id_uuid = uuid.UUID(state["scan_id"])

    # Load completed steps
    steps_stmt = select(ScanStepModel).where(ScanStepModel.scan_id == scan_id_uuid)
    steps = (await db.execute(steps_stmt)).scalars().all()

    # Load existing findings for context
    findings_stmt = select(PentestFindingModel).where(
        PentestFindingModel.scan_id == scan_id_uuid
    )
    findings = (await db.execute(findings_stmt)).scalars().all()

    # Extract port info from nmap findings
    open_ports: list[PortInfo] = []
    technologies: list[str] = []
    tls_issues: list[str] = []
    subdomains: list[str] = []

    for f in findings:
        target = f.target or {}
        if f.tool == "nmap" and target.get("port"):
            open_ports.append(
                PortInfo(
                    port=int(target.get("port", 0)),
                    protocol=target.get("protocol", "tcp"),
                    state="open",
                    service=target.get("service", "unknown"),
                    version=target.get("version", ""),
                    cpe="",
                )
            )
        if f.tool == "httpx":
            tech = (f.evidence or {}).get("technologies", [])
            technologies.extend(tech if isinstance(tech, list) else [])
        if f.tool == "sslyze":
            tls_issues.append(f.title)
        if f.tool == "subfinder":
            hostname = target.get("hostname", "")
            if hostname:
                subdomains.append(hostname)

    technologies = list(set(technologies))[:20]
    subdomains = list(set(subdomains))[:50]

    completed_tools = [s.tool for s in steps if s.finished_at is not None]
    recon_summary = (
        f"Completed tools: {', '.join(completed_tools) or 'none'}. "
        f"Open ports: {len(open_ports)}. "
        f"Subdomains: {len(subdomains)}. "
        f"Technologies: {', '.join(technologies[:5]) or 'unknown'}. "
        f"TLS issues: {len(tls_issues)}. "
        f"Total findings so far: {len(findings)}."
    )

    await log.ainfo("recon_agent_done", scan_id=state["scan_id"], ports=len(open_ports))
    await _emit(state.get("scan_id"), "agent_done", agent="recon",
                summary=f"Found {len(open_ports)} open ports, {len(subdomains)} subdomains, {len(technologies)} technologies.")

    return {
        "open_ports": open_ports,
        "subdomains": subdomains,
        "technologies": technologies,
        "tls_issues": tls_issues,
        "recon_summary": recon_summary,
        "current_agent": "vuln_research",
    }


async def vuln_research_agent(state: PentestState, db: Any) -> dict[str, Any]:
    """RAG-based vuln research: query knowledge base for each discovered service."""
    await _emit(state.get("scan_id"), "agent_start", agent="vuln_research", label="Vuln Research — querying RAG knowledge base")
    from src.adapters.rag.retriever import HybridRetriever
    from src.adapters.rag.embedder import BGEEmbedder

    embedder = BGEEmbedder(ollama_host=get_settings().ollama_host)
    retriever = HybridRetriever(db, embedder)
    vuln_hints: list[VulnHint] = []
    rag_chunks: list[dict[str, Any]] = []

    open_ports = state.get("open_ports", [])
    technologies = state.get("technologies", [])

    # Build search queries from services + technologies
    queries: list[str] = []
    for port_info in open_ports[:10]:
        svc = port_info.get("service", "")
        ver = port_info.get("version", "")
        if svc:
            queries.append(f"{svc} {ver} vulnerability".strip())
    for tech in technologies[:5]:
        queries.append(f"{tech} vulnerability CVE")

    # Deduplicate & cap
    queries = list(dict.fromkeys(queries))[:8]

    for query in queries:
        try:
            results = await retriever.retrieve(query, k=3)
            for chunk in results:
                rag_chunks.append(chunk)
                # Extract CVE if present in metadata
                meta = chunk.get("metadata", {})
                cve = meta.get("cve_id", "")
                cvss = float(meta.get("cvss_v3", 0.0) or 0.0)
                epss = float(meta.get("epss", 0.0) or 0.0)
                kev = bool(meta.get("kev", False))
                if cve:
                    vuln_hints.append(
                        VulnHint(
                            cve=cve,
                            cvss=cvss,
                            epss=epss,
                            kev=kev,
                            description=chunk.get("content", "")[:300],
                            affected_service=query.split()[0],
                        )
                    )
        except Exception as exc:
            log.warning("rag_query_failed", query=query, error=str(exc))

    # Sort by EPSS + KEV priority
    vuln_hints.sort(key=lambda v: (v.get("kev", False), v.get("epss", 0.0)), reverse=True)

    vuln_summary = (
        f"Found {len(vuln_hints)} CVE hints via RAG. "
        f"KEV entries: {sum(1 for v in vuln_hints if v.get('kev'))}. "
        f"High EPSS (>0.5): {sum(1 for v in vuln_hints if v.get('epss', 0) > 0.5)}."
    )

    # Decide whether HITL is needed (any KEV finding or EPSS > 0.7)
    hitl_required = any(v.get("kev") or v.get("epss", 0) > 0.7 for v in vuln_hints)

    await log.ainfo(
        "vuln_research_done",
        scan_id=state["scan_id"],
        hints=len(vuln_hints),
        hitl_required=hitl_required,
    )
    await _emit(state.get("scan_id"), "agent_done", agent="vuln_research",
                summary=f"Found {len(vuln_hints)} CVE hints. HITL required: {hitl_required}.")

    return {
        "vuln_hints": vuln_hints,
        "rag_chunks": rag_chunks[:20],
        "vuln_summary": vuln_summary,
        "hitl_required": hitl_required,
        "current_agent": "hitl_gate" if hitl_required else "attack_planner",
    }


async def hitl_gate_agent(state: PentestState, db: Any) -> dict[str, Any]:
    """Create a HITL approval request and wait for decision via Redis."""
    import redis.asyncio as aioredis

    from src.adapters.db.pentest_models import HitlRequestModel

    settings = get_settings()

    # Create HITL record in DB
    hitl = HitlRequestModel(
        id=uuid.uuid4(),
        scan_id=uuid.UUID(state["scan_id"]),
        action="attack_planner_proceed",
        target_info={
            "target": state.get("target", ""),
            "vuln_count": len(state.get("vuln_hints", [])),
            "kev_count": sum(1 for v in state.get("vuln_hints", []) if v.get("kev")),
        },
        payload=json.dumps(
            {
                "vuln_summary": state.get("vuln_summary", ""),
                "top_cves": [v["cve"] for v in state.get("vuln_hints", [])[:5]],
            }
        ),
        status="pending",
    )
    db.add(hitl)
    await db.commit()

    hitl_id = str(hitl.id)

    # Publish HITL pending event to Redis
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.publish(
            "hitl:pending",
            json.dumps(
                {
                    "hitl_id": hitl_id,
                    "scan_id": state["scan_id"],
                    "action": "attack_planner_proceed",
                }
            ),
        )
        await r.aclose()
    except Exception as exc:
        log.warning("hitl_redis_publish_failed", error=str(exc))

    await log.ainfo("hitl_gate_created", hitl_id=hitl_id, scan_id=state["scan_id"])

    return {
        "hitl_request_id": hitl_id,
        "hitl_approved": None,
        "current_agent": "awaiting_hitl",
    }


async def attack_planner_agent(state: PentestState, db: Any) -> dict[str, Any]:
    """Generate attack scenarios using LLM + MITRE ATT&CK mapping."""
    await _emit(state.get("scan_id"), "agent_start", agent="attack_planner",
                label="Attack Planner — generating MITRE ATT&CK scenarios with Ollama")
    settings = get_settings()

    open_ports = state.get("open_ports", [])
    vuln_hints = state.get("vuln_hints", [])
    technologies = state.get("technologies", [])
    target = state.get("target", "unknown")

    # Build context for LLM
    ports_text = "\n".join(
        f"- Port {p['port']}/{p['protocol']} ({p['service']} {p['version']})".strip()
        for p in open_ports[:15]
    ) or "No ports discovered."

    cves_text = "\n".join(
        f"- {v['cve']} CVSS={v['cvss']:.1f} EPSS={v['epss']:.3f} KEV={v['kev']}: {v['description'][:100]}"
        for v in vuln_hints[:5]
    ) or "No CVEs found."

    system_prompt = (
        "You are a penetration tester. Output ONLY valid JSON. No markdown, no explanations.\n"
        "Schema: {\"scenarios\": [{\"id\": \"s1\", \"title\": str, \"tactic\": str, "
        "\"technique_id\": str, \"technique_name\": str, \"tools\": [str], "
        "\"preconditions\": [str], \"severity\": \"high|medium|low\", \"likelihood\": \"high|medium|low\", "
        "\"steps\": [str]}]}"
    )

    user_prompt = (
        f"Target: {target}. Technologies: {', '.join(technologies[:3]) or 'unknown'}.\n"
        f"Open ports: {ports_text[:300]}\n"
        "Generate 2 attack scenarios as JSON."
    )

    raw = await _ollama_chat(settings.pentest_llm_planner_model, system_prompt, user_prompt, scan_id=state.get("scan_id"))

    attack_scenarios: list[AttackScenario] = []
    try:
        data = json.loads(_extract_json(raw))
        for s in data.get("scenarios", []):
            attack_scenarios.append(
                AttackScenario(
                    id=s.get("id") or str(uuid.uuid4())[:8],
                    title=s.get("title", "Unknown"),
                    tactic=s.get("tactic", ""),
                    technique_id=s.get("technique_id", ""),
                    technique_name=s.get("technique_name", ""),
                    tools=s.get("tools", []),
                    preconditions=s.get("preconditions", []),
                    severity=s.get("severity", "medium"),
                    likelihood=s.get("likelihood", "medium"),
                    steps=s.get("steps", []),
                )
            )
    except Exception as exc:
        log.warning("attack_planner_parse_error", error=str(exc))

    # Always fall back to a stub when LLM produced no scenarios
    if not attack_scenarios:
        # Build a context-aware stub from discovered ports/technologies
        top_service = open_ports[0]["service"] if open_ports else "web application"
        attack_scenarios = [
            AttackScenario(
                id="stub-001",
                title=f"Service Exploitation — {top_service}",
                tactic="Initial Access",
                technique_id="T1190",
                technique_name="Exploit Public-Facing Application",
                tools=["nuclei", "nmap", "metasploit"],
                preconditions=["Reachable target", f"Open port on {top_service}"],
                severity="high",
                likelihood="medium",
                steps=[
                    f"Enumerate {top_service} service version",
                    "Search for known CVEs/exploits",
                    "Attempt exploitation",
                    "Post-exploitation: privilege escalation",
                ],
            )
        ]

    # Build Pentesting Task Tree
    ptt = {
        "version": "1.0",
        "scan_id": state["scan_id"],
        "target": target,
        "phases": {
            "recon": {"status": "done", "summary": state.get("recon_summary", "")},
            "vuln_research": {"status": "done", "summary": state.get("vuln_summary", "")},
            "attack_planning": {
                "status": "done",
                "scenarios_count": len(attack_scenarios),
            },
        },
        "scenarios": [dict(s) for s in attack_scenarios],
    }

    await log.ainfo(
        "attack_planner_done",
        scan_id=state["scan_id"],
        scenarios=len(attack_scenarios),
    )
    await _emit(state.get("scan_id"), "agent_done", agent="attack_planner",
                summary=f"Generated {len(attack_scenarios)} attack scenarios.")

    return {
        "attack_scenarios": attack_scenarios,
        "ptt": ptt,
        "current_agent": "reporter",
    }


async def reporter_agent(state: PentestState, db: Any) -> dict[str, Any]:
    """Generate bilingual (EN + PL) executive summary from all findings."""
    await _emit(state.get("scan_id"), "agent_start", agent="reporter",
                label="Reporter — writing executive summary (EN + PL)")
    settings = get_settings()

    scenarios = state.get("attack_scenarios", [])
    vuln_hints = state.get("vuln_hints", [])
    target = state.get("target", "unknown")

    severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for s in scenarios:
        sev = s.get("severity", "medium").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    kev_count = sum(1 for v in vuln_hints if v.get("kev"))
    top_findings = [s["title"] for s in scenarios[:5]]

    risk_level = (
        "critical" if severity_counts["critical"] > 0
        else "high" if severity_counts["high"] > 0
        else "medium" if severity_counts["medium"] > 0
        else "low"
    )

    system_en = (
        "You are a cybersecurity expert. Output ONLY valid JSON, no markdown.\n"
        "Schema: {\"summary\": str, \"key_findings\": [str], \"recommended_actions\": [str]}"
    )
    user_en = (
        f"Target: {target}. Risk: {risk_level}. "
        f"Findings: {', '.join(top_findings[:2]) or 'open ports detected'}. "
        "Write a 2-sentence executive summary as JSON."
    )

    await _emit(state.get("scan_id"), "llm_phase", phase="EN executive summary")
    raw_en = await _ollama_chat(settings.pentest_llm_reporter_model, system_en, user_en, scan_id=state.get("scan_id"))

    try:
        data_en = json.loads(_extract_json(raw_en))
        exec_summary_en = data_en.get("summary", "Pentest completed. Review findings.")
        key_findings = data_en.get("key_findings", top_findings[:3])
        recommended_actions = data_en.get("recommended_actions", [])
    except Exception:
        exec_summary_en = "Pentest completed. Review detailed findings."
        key_findings = top_findings[:3]
        recommended_actions = ["Review and remediate high-severity findings."]

    # PL summary: simple fallback without a second LLM call to keep latency reasonable
    exec_summary_pl = f"Test penetracyjny dla {target} zakończony. Poziom ryzyka: {risk_level}. {exec_summary_en}"

    await log.ainfo("reporter_agent_done", scan_id=state["scan_id"], risk_level=risk_level)
    await _emit(state.get("scan_id"), "agent_done", agent="reporter",
                summary=f"Risk level: {risk_level}. Summary written.")

    return {
        "exec_summary_en": exec_summary_en,
        "exec_summary_pl": exec_summary_pl,
        "risk_level": risk_level,
        "key_findings": key_findings,
        "recommended_actions": recommended_actions,
        "completed": True,
        "current_agent": "done",
    }
