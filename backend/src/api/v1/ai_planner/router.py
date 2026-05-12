"""AI Planner API — LangGraph multi-agent analysis endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai.langgraph import PentestAgentGraph
from src.dependencies import get_db
from src.adapters.db.pentest_models import PentestScanModel
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class PlannerRunResponse(BaseModel):
    scan_id: str
    status: str             # running / awaiting_hitl / done / error
    current_agent: str
    recon_summary: str | None = None
    vuln_summary: str | None = None
    hitl_required: bool = False
    hitl_request_id: str | None = None
    attack_scenarios_count: int = 0
    exec_summary_en: str | None = None
    exec_summary_pl: str | None = None
    risk_level: str | None = None
    error: str | None = None


class AttackScenarioOut(BaseModel):
    id: str
    title: str
    tactic: str
    technique_id: str
    technique_name: str
    tools: list[str]
    preconditions: list[str]
    severity: str
    likelihood: str
    steps: list[str]


class PlannerDetailResponse(BaseModel):
    scan_id: str
    open_ports: list[dict[str, Any]]
    subdomains: list[str]
    technologies: list[str]
    attack_scenarios: list[AttackScenarioOut]
    exec_summary_en: str | None
    exec_summary_pl: str | None
    risk_level: str | None
    key_findings: list[str]
    recommended_actions: list[str]
    ptt: dict[str, Any] | None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/scans/{scan_id}/ai-planner/run",
    response_model=PlannerRunResponse,
    summary="Run LangGraph multi-agent analysis on a completed scan",
)
async def run_ai_planner(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> PlannerRunResponse:
    """Trigger the multi-agent pipeline: Recon → VulnResearch → HITL → AttackPlanner → Reporter."""
    stmt = select(PentestScanModel).where(PentestScanModel.id == uuid.UUID(scan_id))
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    if scan.status not in ("done", "running"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scan must be in 'done' or 'running' status, got '{scan.status}'",
        )

    # Load target value
    from src.adapters.db.pentest_models import TargetModel
    tgt_stmt = select(TargetModel).where(TargetModel.id == scan.target_id)
    target = (await db.execute(tgt_stmt)).scalar_one_or_none()
    target_value = target.value if target else "unknown"

    graph = PentestAgentGraph()
    final_state = await graph.run(
        scan_id=scan_id,
        engagement_id=str(scan.engagement_id),
        target=target_value,
        profile=scan.profile,
        db=db,
        selected_modules=scan.selected_modules or [],
    )

    # Persist PTT to scan
    if final_state.get("ptt"):
        scan.ptt = final_state["ptt"]
        await db.commit()

    current = final_state.get("current_agent", "done")
    if current == "awaiting_hitl":
        run_status = "awaiting_hitl"
    elif final_state.get("completed"):
        run_status = "done"
    elif final_state.get("error"):
        run_status = "error"
    else:
        run_status = "running"

    return PlannerRunResponse(
        scan_id=scan_id,
        status=run_status,
        current_agent=current,
        recon_summary=final_state.get("recon_summary"),
        vuln_summary=final_state.get("vuln_summary"),
        hitl_required=final_state.get("hitl_required", False),
        hitl_request_id=final_state.get("hitl_request_id"),
        attack_scenarios_count=len(final_state.get("attack_scenarios", [])),
        exec_summary_en=final_state.get("exec_summary_en"),
        exec_summary_pl=final_state.get("exec_summary_pl"),
        risk_level=final_state.get("risk_level"),
        error=final_state.get("error"),
    )


@router.get(
    "/scans/{scan_id}/ai-planner/result",
    response_model=PlannerDetailResponse,
    summary="Get full AI planner result for a scan (PTT + scenarios + summaries)",
)
async def get_planner_result(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> PlannerDetailResponse:
    """Return stored PTT and attack scenarios from scan.ptt column."""
    stmt = select(PentestScanModel).where(PentestScanModel.id == uuid.UUID(scan_id))
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    ptt: dict[str, Any] = scan.ptt or {}
    scenarios_raw = ptt.get("scenarios", [])

    scenarios_out = [
        AttackScenarioOut(
            id=s.get("id", ""),
            title=s.get("title", ""),
            tactic=s.get("tactic", ""),
            technique_id=s.get("technique_id", ""),
            technique_name=s.get("technique_name", ""),
            tools=s.get("tools", []),
            preconditions=s.get("preconditions", []),
            severity=s.get("severity", "medium"),
            likelihood=s.get("likelihood", "medium"),
            steps=s.get("steps", []),
        )
        for s in scenarios_raw
    ]

    phases = ptt.get("phases", {})
    recon_phase = phases.get("recon", {})

    return PlannerDetailResponse(
        scan_id=scan_id,
        open_ports=ptt.get("open_ports", []),
        subdomains=ptt.get("subdomains", []),
        technologies=ptt.get("technologies", []),
        attack_scenarios=scenarios_out,
        exec_summary_en=ptt.get("exec_summary_en"),
        exec_summary_pl=ptt.get("exec_summary_pl"),
        risk_level=ptt.get("risk_level"),
        key_findings=ptt.get("key_findings", []),
        recommended_actions=ptt.get("recommended_actions", []),
        ptt=ptt if ptt else None,
    )


@router.get(
    "/scans/{scan_id}/ports",
    summary="Get discovered open ports from scan nmap results",
)
async def get_scan_ports(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Return structured port data from nmap findings for the attack planner UI."""
    from src.adapters.db.pentest_models import PentestFindingModel

    stmt = select(PentestFindingModel).where(
        PentestFindingModel.scan_id == uuid.UUID(scan_id),
        PentestFindingModel.tool == "nmap",
    )
    findings = (await db.execute(stmt)).scalars().all()

    ports = []
    for f in findings:
        target = f.target or {}
        if target.get("port"):
            ports.append({
                "port": target.get("port"),
                "protocol": target.get("protocol", "tcp"),
                "service": target.get("service", "unknown"),
                "version": target.get("version", ""),
                "state": "open",
                "finding_id": str(f.id),
                "severity": f.severity,
                "cve": f.cve or [],
            })

    # Sort by port number
    ports.sort(key=lambda p: int(p.get("port", 0)))

    return {"scan_id": scan_id, "ports": ports, "total": len(ports)}


@router.get(
    "/scans/{scan_id}/attack-scenarios",
    summary="Get AI-generated attack scenarios from the PTT",
)
async def get_attack_scenarios(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Return attack scenarios from the stored Pentesting Task Tree."""
    stmt = select(PentestScanModel).where(PentestScanModel.id == uuid.UUID(scan_id))
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    ptt = scan.ptt or {}
    scenarios = ptt.get("scenarios", [])

    return {
        "scan_id": scan_id,
        "scenarios": scenarios,
        "total": len(scenarios),
        "risk_level": ptt.get("risk_level"),
    }


@router.get(
    "/scans/{scan_id}/ai-planner/stream",
    summary="SSE stream of AI planner progress — run analysis and stream live events",
)
async def stream_ai_planner(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> StreamingResponse:
    """Subscribe to SSE events for the AI planner pipeline.

    Triggers the analysis pipeline and streams events:
    - agent_start / agent_done (per LangGraph node)
    - llm_phase (LLM subphase label)
    - token (streamed Ollama tokens)
    - complete (final result)
    - error (on failure)
    """
    stmt = select(PentestScanModel).where(PentestScanModel.id == uuid.UUID(scan_id))
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    if scan.status not in ("done", "running"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Scan must be done to run AI analysis, got '{scan.status}'",
        )

    from src.adapters.db.pentest_models import TargetModel
    tgt_stmt = select(TargetModel).where(TargetModel.id == scan.target_id)
    target = (await db.execute(tgt_stmt)).scalar_one_or_none()
    target_value = target.value if target else "unknown"

    scan_engagement_id = str(scan.engagement_id)
    scan_profile = scan.profile
    scan_modules = scan.selected_modules or []

    async def _event_stream() -> AsyncGenerator[str, None]:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        channel = f"pentest:ai:{scan_id}:stream"

        # Create a new DB session for the background graph task
        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession, create_async_engine, async_sessionmaker
        engine = create_async_engine(settings.postgres_dsn, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        # Subscribe to Redis BEFORE starting the graph
        redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis_conn.pubsub()
        await pubsub.subscribe(channel)

        done_event = asyncio.Event()
        error_holder: list[str] = []

        async def run_graph() -> None:
            async with session_factory() as graph_db:
                try:
                    graph = PentestAgentGraph()
                    final_state = await graph.run(
                        scan_id=scan_id,
                        engagement_id=scan_engagement_id,
                        target=target_value,
                        profile=scan_profile,
                        db=graph_db,
                        selected_modules=scan_modules,
                    )
                    # Persist PTT
                    if final_state.get("ptt"):
                        from sqlalchemy import select as sa_select
                        from src.adapters.db.pentest_models import PentestScanModel as _ScanModel
                        s = (await graph_db.execute(
                            sa_select(_ScanModel).where(_ScanModel.id == uuid.UUID(scan_id))
                        )).scalar_one_or_none()
                        if s:
                            ptt = final_state["ptt"]
                            ptt["open_ports"] = [dict(p) for p in final_state.get("open_ports", [])]
                            ptt["subdomains"] = final_state.get("subdomains", [])
                            ptt["technologies"] = final_state.get("technologies", [])
                            ptt["exec_summary_en"] = final_state.get("exec_summary_en")
                            ptt["exec_summary_pl"] = final_state.get("exec_summary_pl")
                            ptt["risk_level"] = final_state.get("risk_level")
                            ptt["key_findings"] = final_state.get("key_findings", [])
                            ptt["recommended_actions"] = final_state.get("recommended_actions", [])
                            s.ptt = ptt
                            await graph_db.commit()
                    # Publish complete event
                    await redis_conn.publish(channel, json.dumps({
                        "type": "complete",
                        "scenarios": len(final_state.get("attack_scenarios", [])),
                        "risk_level": final_state.get("risk_level"),
                        "exec_summary_en": final_state.get("exec_summary_en"),
                    }))
                except Exception as exc:
                    error_holder.append(str(exc))
                    await redis_conn.publish(channel, json.dumps({"type": "error", "message": str(exc)}))
                finally:
                    done_event.set()
                    await engine.dispose()

        # Start graph in background
        task = asyncio.create_task(run_graph())

        # Heartbeat every 15s to keep connection alive
        last_msg = asyncio.get_event_loop().time()

        try:
            while True:
                try:
                    message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), timeout=2.0)
                except asyncio.TimeoutError:
                    message = None

                now = asyncio.get_event_loop().time()
                if message is None:
                    if now - last_msg > 10:
                        yield "event: heartbeat\ndata: {}\n\n"
                        last_msg = now
                    if done_event.is_set():
                        break
                    continue

                last_msg = now
                data_str = message.get("data", "")
                if not data_str:
                    continue

                try:
                    evt = json.loads(data_str)
                except Exception:
                    continue

                yield f"data: {json.dumps(evt)}\n\n"

                if evt.get("type") in ("complete", "error"):
                    break

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await redis_conn.aclose()
            if not task.done():
                task.cancel()

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
