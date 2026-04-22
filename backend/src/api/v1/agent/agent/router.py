"""AI Agent router — natural language interface to all platform capabilities.

Uses Anthropic Claude with tool use to execute real platform operations:
- OSINT scans (email, domain, IP, username, phone)
- Pentest / port scans
- Results retrieval and summarization
- Recent activity listing
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, AsyncGenerator

import anthropic
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.config import get_settings
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["agent"])

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI-powered security operations assistant for an OSINT and penetration testing platform.

You can execute real operations on the platform using the provided tools:
- Run OSINT scans on emails, domains, IPs, usernames, phone numbers
- Run port/pentest scans on domains or IPs
- Retrieve scan results and findings
- List recent investigations and scans

Guidelines:
- When a user asks to scan/investigate/check something, immediately use the appropriate tool.
- After executing a tool, present results in a clear, structured format using markdown.
- For OSINT scans: use run_osint_scan. For port scans or "what's running on": use run_port_scan.
- If the user asks for a "quick check", run one targeted scan. For "full scan" suggest multiple.
- Be concise and actionable. Focus on security-relevant findings.
- Format IPs, domains, CVEs, ports in `code` style for readability.
- If no API keys are configured for a scanner, mention it briefly but still start the scan.
"""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "run_osint_scan",
        "description": (
            "Run an OSINT investigation on a target. Creates a new investigation and immediately starts "
            "scanning across all configured OSINT sources. "
            "Use for: email addresses, domains, IP addresses, usernames, phone numbers, NIP numbers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The target to investigate (email, domain, IP, username, phone, etc.)",
                },
                "target_type": {
                    "type": "string",
                    "enum": ["email", "domain", "ip_address", "username", "phone", "auto"],
                    "description": "Type of target. Use 'auto' to detect automatically.",
                },
                "investigation_name": {
                    "type": "string",
                    "description": "Optional custom name for this investigation",
                },
            },
            "required": ["target", "target_type"],
        },
    },
    {
        "name": "run_port_scan",
        "description": (
            "Run a port scan and service discovery on a domain or IP address. "
            "Uses nmap, subfinder, httpx, nuclei and other tools to discover open ports, "
            "running services, subdomains, and vulnerabilities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Domain or IP address to scan",
                },
                "profile": {
                    "type": "string",
                    "enum": ["quick", "standard", "deep"],
                    "description": "Scan depth: quick (fast top ports), standard (balanced), deep (full + scripts)",
                },
                "modules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific modules to run. Options: nmap, subfinder, httpx, nuclei, sslyze, gobuster",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "get_scan_results",
        "description": (
            "Get results and findings from a previous scan or investigation. "
            "Returns a structured summary of what was found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The investigation ID or pentest scan ID",
                },
                "result_type": {
                    "type": "string",
                    "enum": ["osint", "pentest"],
                    "description": "Whether this is an OSINT investigation or a pentest scan",
                },
            },
            "required": ["id", "result_type"],
        },
    },
    {
        "name": "list_recent_activity",
        "description": (
            "List recent OSINT investigations and pentest scans. "
            "Use to get an overview of recent activity or to find scan IDs for follow-up."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent items to show (default 5, max 20)",
                },
            },
        },
    },
    {
        "name": "get_pentest_findings",
        "description": (
            "Get vulnerability findings from a pentest scan. "
            "Returns discovered vulnerabilities with severity, description, and remediation advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scan_id": {
                    "type": "string",
                    "description": "The pentest scan ID",
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "all"],
                    "description": "Filter by severity (default: all)",
                },
            },
            "required": ["scan_id"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class AgentMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=20000)


class AgentChatRequest(BaseModel):
    messages: list[AgentMessage] = Field(..., min_length=1, max_length=100)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detect_input_type(target: str) -> str:
    """Auto-detect the type of a scan target."""
    target = target.strip().lower()
    if "@" in target:
        return "email"
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}(/\d+)?$", target):
        return "ip_address"
    if re.match(r"^\+?[\d\s\-()]{7,15}$", target):
        return "phone"
    if re.match(r"^\d{10}$", target):
        return "nip"
    if "." in target:
        return "domain"
    return "username"


async def _noop_publish(event: Any) -> None:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────

async def _exec_run_osint_scan(inputs: dict[str, Any], db: AsyncSession, user: User) -> dict[str, Any]:
    from src.adapters.db.repositories import SqlAlchemyInvestigationRepository
    from src.core.use_cases.create_investigation import CreateInvestigation, CreateInvestigationInput
    from src.core.domain.entities.types import ScanInputType, SeedInput
    from src.adapters.db.models import InvestigationModel

    target = inputs["target"].strip()
    target_type = inputs.get("target_type", "auto")
    if target_type == "auto":
        target_type = _detect_input_type(target)

    try:
        input_type = ScanInputType(target_type)
    except ValueError:
        input_type = ScanInputType.DOMAIN

    name = inputs.get("investigation_name") or f"AI: {target}"
    seed = SeedInput(value=target, input_type=input_type)

    repo = SqlAlchemyInvestigationRepository(db)
    uc = CreateInvestigation(repo, _noop_publish)
    investigation = await uc.execute(
        CreateInvestigationInput(
            title=name,
            description="Initiated by AI agent",
            owner_id=user.id,
            seed_inputs=[seed],
        )
    )

    # Mark as running in DB
    inv_model = await db.get(InvestigationModel, investigation.id)
    if inv_model:
        inv_model.status = "running"
        await db.commit()

    # Launch scan in background (fire-and-forget)
    from src.api.v1.investigations.router import _run_scans_background
    asyncio.create_task(_run_scans_background(investigation.id, [seed]))

    return {
        "investigation_id": str(investigation.id),
        "target": target,
        "target_type": input_type.value,
        "status": "running",
        "message": f"OSINT scan started for `{target}` (type: {input_type.value}). Investigation ID: `{investigation.id}`",
    }


async def _exec_run_port_scan(inputs: dict[str, Any], db: AsyncSession, user: User) -> dict[str, Any]:
    from src.adapters.db.pentest_models import EngagementModel, TargetModel, PentestScanModel
    from src.workers.pentest_orchestrator import orchestrate_scan

    target = inputs["target"].strip()
    profile = inputs.get("profile", "standard")
    modules: list[str] = inputs.get("modules") or ["nmap", "subfinder", "httpx", "nuclei"]

    # Find or create the shared "AI Agent Scans" engagement
    result = await db.execute(
        select(EngagementModel)
        .where(EngagementModel.name == "AI Agent Scans", EngagementModel.status == "active")
        .limit(1)
    )
    engagement = result.scalar_one_or_none()

    if engagement is None:
        engagement = EngagementModel(
            id=uuid.uuid4(),
            created_by=user.id,
            name="AI Agent Scans",
            client_name="AI Agent",
            scope_rules={"allow_all": True, "domains": ["*"], "ips": ["*"]},
            status="active",
        )
        db.add(engagement)
        await db.flush()

    # Detect target type
    target_type = "ip" if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target) else "domain"

    tgt = TargetModel(
        id=uuid.uuid4(),
        engagement_id=engagement.id,
        type=target_type,
        value=target,
    )
    db.add(tgt)
    await db.flush()

    scan = PentestScanModel(
        id=uuid.uuid4(),
        engagement_id=engagement.id,
        target_id=tgt.id,
        user_id=user.id,
        profile=profile,
        selected_modules=modules,
        status="queued",
        progress_pct=0,
    )
    db.add(scan)
    await db.commit()

    orchestrate_scan.apply_async(args=[str(scan.id)], queue="pentest_heavy")

    return {
        "scan_id": str(scan.id),
        "engagement_id": str(engagement.id),
        "target": target,
        "target_type": target_type,
        "profile": profile,
        "modules": modules,
        "status": "queued",
        "message": (
            f"Port scan queued for `{target}` with profile `{profile}`. "
            f"Modules: {', '.join(f'`{m}`' for m in modules)}. "
            f"Scan ID: `{scan.id}`"
        ),
    }


async def _exec_get_scan_results(inputs: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    result_id = inputs["id"].strip()
    result_type = inputs.get("result_type", "osint")

    if result_type == "osint":
        from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository

        try:
            inv_id = uuid.UUID(result_id)
        except ValueError:
            return {"error": f"Invalid investigation ID: {result_id}"}

        repo = SqlAlchemyScanResultRepository(db)
        results = await repo.get_by_investigation(inv_id)

        findings: list[dict[str, Any]] = []
        for r in results:
            if r.status == "success" and r.extracted_identifiers:
                findings.append({
                    "scanner": r.scanner_name,
                    "findings_count": len(r.extracted_identifiers),
                    "sample": r.extracted_identifiers[:3],
                })

        return {
            "investigation_id": result_id,
            "total_scanners_run": len(results),
            "successful_scanners": sum(1 for r in results if r.status == "success"),
            "failed_scanners": sum(1 for r in results if r.status == "failed"),
            "top_findings": findings[:10],
        }

    else:  # pentest
        from src.adapters.db.pentest_models import PentestFindingModel, PentestScanModel

        try:
            scan_id = uuid.UUID(result_id)
        except ValueError:
            return {"error": f"Invalid scan ID: {result_id}"}

        scan_result = await db.execute(
            select(PentestScanModel).where(PentestScanModel.id == scan_id)
        )
        scan = scan_result.scalar_one_or_none()
        if scan is None:
            return {"error": "Scan not found"}

        findings_result = await db.execute(
            select(PentestFindingModel)
            .where(PentestFindingModel.scan_id == scan_id)
            .limit(20)
        )
        findings_list = findings_result.scalars().all()

        severity_counts: dict[str, int] = {}
        for f in findings_list:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        return {
            "scan_id": result_id,
            "scan_status": scan.status,
            "progress_pct": scan.progress_pct,
            "severity_breakdown": severity_counts,
            "total_findings": len(findings_list),
            "top_findings": [
                {
                    "title": f.title,
                    "severity": f.severity,
                    "tool": f.tool,
                    "status": f.status,
                }
                for f in findings_list[:5]
            ],
        }


async def _exec_list_recent_activity(inputs: dict[str, Any], db: AsyncSession, user: User) -> dict[str, Any]:
    from src.adapters.db.models import InvestigationModel
    from src.adapters.db.pentest_models import PentestScanModel

    limit = min(int(inputs.get("limit") or 5), 20)

    # Recent investigations
    inv_result = await db.execute(
        select(InvestigationModel)
        .where(InvestigationModel.owner_id == user.id)
        .order_by(desc(InvestigationModel.created_at))
        .limit(limit)
    )
    investigations = inv_result.scalars().all()

    # Recent pentest scans
    scans_result = await db.execute(
        select(PentestScanModel)
        .where(PentestScanModel.user_id == user.id)
        .order_by(desc(PentestScanModel.created_at))
        .limit(limit)
    )
    pentest_scans = scans_result.scalars().all()

    return {
        "investigations": [
            {
                "id": str(inv.id),
                "title": inv.title,
                "status": inv.status,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            }
            for inv in investigations
        ],
        "pentest_scans": [
            {
                "id": str(s.id),
                "status": s.status,
                "profile": s.profile,
                "progress_pct": s.progress_pct,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in pentest_scans
        ],
    }


async def _exec_get_pentest_findings(inputs: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    from src.adapters.db.pentest_models import PentestFindingModel

    try:
        scan_id = uuid.UUID(inputs["scan_id"])
    except ValueError:
        return {"error": f"Invalid scan ID: {inputs['scan_id']}"}

    severity_filter = inputs.get("severity", "all")

    stmt = select(PentestFindingModel).where(PentestFindingModel.scan_id == scan_id)
    if severity_filter and severity_filter != "all":
        stmt = stmt.where(PentestFindingModel.severity == severity_filter)
    stmt = stmt.order_by(
        PentestFindingModel.severity.in_(["critical", "high", "medium", "low", "info"])
    ).limit(30)

    result = await db.execute(stmt)
    findings = result.scalars().all()

    return {
        "scan_id": str(scan_id),
        "severity_filter": severity_filter,
        "total": len(findings),
        "findings": [
            {
                "id": str(f.id),
                "title": f.title,
                "severity": f.severity,
                "tool": f.tool,
                "status": f.status,
                "description": (f.description or "")[:200],
                "cve": f.cve,
                "url": f.url,
            }
            for f in findings
        ],
    }


async def _execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    db: AsyncSession,
    user: User,
) -> str:
    """Dispatch a tool call and return the result as a JSON string."""
    try:
        if tool_name == "run_osint_scan":
            result = await _exec_run_osint_scan(tool_input, db, user)
        elif tool_name == "run_port_scan":
            result = await _exec_run_port_scan(tool_input, db, user)
        elif tool_name == "get_scan_results":
            result = await _exec_get_scan_results(tool_input, db)
        elif tool_name == "list_recent_activity":
            result = await _exec_list_recent_activity(tool_input, db, user)
        elif tool_name == "get_pentest_findings":
            result = await _exec_get_pentest_findings(tool_input, db)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except Exception as exc:
        log.exception("agent_tool_error", tool=tool_name, error=str(exc))
        result = {"error": str(exc)}

    return json.dumps(result, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# SSE streaming generator
# ─────────────────────────────────────────────────────────────────────────────

async def _agent_stream(
    messages: list[dict[str, Any]],
    db: AsyncSession,
    user: User,
) -> AsyncGenerator[str, None]:
    """Run the Claude agent loop and yield SSE events."""
    settings = get_settings()

    if not settings.anthropic_api_key:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env'})}\n\n"
        return

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    model = "claude-sonnet-4-6" if "4" in settings.anthropic_model else settings.anthropic_model

    # Agentic loop — supports multi-turn tool use
    current_messages = list(messages)

    for _turn in range(10):  # max 10 tool rounds
        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=current_messages,
            tools=TOOLS,  # type: ignore[arg-type]
        ) as stream:
            tool_uses: list[dict[str, Any]] = []
            current_tool_input_json = ""
            current_tool_id = ""
            current_tool_name = ""

            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        current_tool_input_json = ""
                        yield f"data: {json.dumps({'type': 'tool_start', 'tool': current_tool_name, 'tool_id': current_tool_id})}\n\n"

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield f"data: {json.dumps({'type': 'text_delta', 'content': event.delta.text})}\n\n"
                    elif event.delta.type == "input_json_delta":
                        current_tool_input_json += event.delta.partial_json

                elif event.type == "content_block_stop":
                    if current_tool_name:
                        # Parse accumulated tool input
                        try:
                            tool_input = json.loads(current_tool_input_json) if current_tool_input_json else {}
                        except json.JSONDecodeError:
                            tool_input = {}

                        tool_uses.append({
                            "id": current_tool_id,
                            "name": current_tool_name,
                            "input": tool_input,
                        })
                        yield f"data: {json.dumps({'type': 'tool_input', 'tool': current_tool_name, 'tool_id': current_tool_id, 'input': tool_input})}\n\n"
                        current_tool_name = ""
                        current_tool_id = ""
                        current_tool_input_json = ""

                elif event.type == "message_stop":
                    pass

            final_message = await stream.get_final_message()

        # If no tool calls, we're done
        if not tool_uses:
            break

        # Execute all tools and collect results
        assistant_content = final_message.content
        tool_results = []

        for tool_call in tool_uses:
            result_str = await _execute_tool(tool_call["name"], tool_call["input"], db, user)
            result_data = json.loads(result_str)

            yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_call['name'], 'tool_id': tool_call['id'], 'result': result_data})}\n\n"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_call["id"],
                "content": result_str,
            })

        # Add assistant message + tool results to continue the conversation
        current_messages.append({"role": "assistant", "content": assistant_content})
        current_messages.append({"role": "user", "content": tool_results})

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/agent/chat",
    summary="Stream an AI agent response with tool execution",
    response_class=StreamingResponse,
)
async def agent_chat(
    body: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream Claude agent responses over SSE.

    Events:
    - ``{"type": "text_delta", "content": "..."}`` — streamed text token
    - ``{"type": "tool_start", "tool": "run_osint_scan", "tool_id": "..."}`` — tool beginning
    - ``{"type": "tool_input", "tool": "...", "input": {...}}`` — resolved tool inputs
    - ``{"type": "tool_result", "tool": "...", "result": {...}}`` — tool execution result
    - ``{"type": "done"}`` — stream complete
    - ``{"type": "error", "content": "..."}`` — fatal error
    """
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    return StreamingResponse(
        _agent_stream(messages, db, current_user),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
