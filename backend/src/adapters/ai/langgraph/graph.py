"""PentestAgentGraph — sequential multi-agent state machine.

Topology:
  recon → vuln_research → [hitl_gate if needed] → attack_planner → reporter

Each node is an async agent function from agents.py.  The graph is driven by
the `current_agent` field in PentestState, which each agent sets to name the
next node to execute.

This implementation does NOT require the langgraph package — it uses a simple
async loop with conditional routing, which is API-compatible with a future
langgraph.StateGraph migration.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from .agents import (
    attack_planner_agent,
    hitl_gate_agent,
    recon_agent,
    reporter_agent,
    vuln_research_agent,
)
from .state import PentestState

log = structlog.get_logger(__name__)


class PentestAgentGraph:
    """Orchestrates multi-agent pentest analysis for a completed scan.

    Usage::

        graph = PentestAgentGraph()
        final_state = await graph.run(scan_id="...", db=db_session)
    """

    _NODES = {
        "recon": recon_agent,
        "vuln_research": vuln_research_agent,
        "hitl_gate": hitl_gate_agent,
        "attack_planner": attack_planner_agent,
        "reporter": reporter_agent,
    }

    # Nodes that require HITL approval before proceeding
    _HITL_BEFORE = {"attack_planner"}

    async def run(
        self,
        scan_id: str,
        engagement_id: str,
        target: str,
        profile: str,
        db: Any,
        selected_modules: list[str] | None = None,
        max_steps: int = 20,
    ) -> PentestState:
        """Run the full multi-agent pipeline and return final state."""

        state: PentestState = {
            "scan_id": scan_id,
            "engagement_id": engagement_id,
            "target": target,
            "profile": profile,
            "selected_modules": selected_modules or [],
            "current_agent": "recon",
            "hitl_required": False,
            "hitl_request_id": None,
            "hitl_approved": None,
            "completed": False,
            "error": None,
        }

        steps_taken = 0

        while not state.get("completed") and steps_taken < max_steps:
            current = state.get("current_agent", "done")

            if current in ("done", "awaiting_hitl"):
                break

            agent_fn = self._NODES.get(current)
            if agent_fn is None:
                await log.aerror("unknown_agent_node", node=current, scan_id=scan_id)
                state["error"] = f"Unknown agent node: {current}"
                break

            await log.ainfo("agent_node_start", node=current, scan_id=scan_id)

            try:
                update = await agent_fn(state, db)
                state.update(update)
            except Exception as exc:
                await log.aerror("agent_node_error", node=current, scan_id=scan_id, error=str(exc))
                state["error"] = str(exc)
                state["completed"] = True
                break

            steps_taken += 1

        return state

    async def resume_after_hitl(
        self,
        scan_id: str,
        hitl_request_id: str,
        approved: bool,
        state: PentestState,
        db: Any,
    ) -> PentestState:
        """Resume graph execution after a HITL gate is resolved."""
        state["hitl_approved"] = approved
        state["hitl_request_id"] = hitl_request_id

        if not approved:
            state["completed"] = True
            state["exec_summary_en"] = "Scan halted at HITL gate — operator rejected exploit planning."
            state["exec_summary_pl"] = "Skanowanie zatrzymane na bramce HITL — operator odrzucił planowanie eksploitacji."
            state["current_agent"] = "done"
            return state

        # Approved — continue from attack_planner
        state["current_agent"] = "attack_planner"
        return await self.run(
            scan_id=scan_id,
            engagement_id=state.get("engagement_id", ""),
            target=state.get("target", ""),
            profile=state.get("profile", "standard"),
            db=db,
            selected_modules=state.get("selected_modules"),
        )
