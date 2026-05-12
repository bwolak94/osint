"""AttackChainService — LLM-powered MITRE ATT&CK kill-chain generator."""

from __future__ import annotations

import json
import uuid

import structlog

from src.adapters.ai.pentest_llm_service import PentestLLMService
from src.adapters.ai.schemas.pentest import AttackChain, AttackStep

log = structlog.get_logger(__name__)


class AttackChainService:
    """Generates attack chains from confirmed pentest findings via the LLM planner."""

    def __init__(self, llm_service: PentestLLMService) -> None:
        self._llm = llm_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_chain(
        self,
        findings: list[dict],
        engagement_context: str = "",
    ) -> AttackChain:
        """Return an AttackChain mapped to MITRE ATT&CK v17 for the given findings.

        Falls back to a minimal stub if the LLM call fails or returns unparseable JSON.
        """
        findings_text = self._format_findings(findings)

        system_prompt = (
            f"{engagement_context}\n\nYou are a threat modeling analyst expert in MITRE ATT&CK v17."
            if engagement_context
            else "You are a threat modeling analyst expert in MITRE ATT&CK v17."
        )

        user_prompt = (
            "Given these confirmed findings, build a realistic attack chain mapped to MITRE ATT&CK v17.\n"
            "Requirements:\n"
            "  - Output of step N must be a precondition for step N+1.\n"
            "  - Focus on techniques with known PoC exploits.\n"
            "  - Only include steps achievable given the findings.\n"
            "  - Return a single JSON object matching the AttackChain schema exactly.\n\n"
            "AttackChain schema:\n"
            "{\n"
            '  "chain_id": "<string>",\n'
            '  "objective_en": "<string>",\n'
            '  "target_assets": ["<string>", ...],\n'
            '  "steps": [\n'
            "    {\n"
            '      "step": <int>,\n'
            '      "tactic": "<string>",\n'
            '      "technique_id": "<string>",\n'
            '      "technique_name": "<string>",\n'
            '      "sub_technique_id": null,\n'
            '      "description_en": "<string>",\n'
            '      "preconditions": ["<string>", ...],\n'
            '      "tools": ["<string>", ...],\n'
            '      "detection_hints": ["<string>", ...]\n'
            "    }\n"
            "  ],\n"
            '  "overall_likelihood": "low|medium|high",\n'
            '  "overall_impact": "critical|high|medium|low|info",\n'
            '  "kill_chain_phases": ["<string>", ...]\n'
            "}\n\n"
            f"Findings:\n{findings_text}"
        )

        raw = await self._llm._chat(
            model=self._llm._planner_model,
            system=system_prompt,
            user=user_prompt,
        )

        try:
            data = json.loads(raw)
            # Ensure chain_id is present — generate one if LLM omitted it
            if not data.get("chain_id"):
                data["chain_id"] = str(uuid.uuid4())
            return AttackChain.model_validate(data)
        except Exception as exc:
            await log.aerror(
                "attack_chain_parse_error",
                error=str(exc),
                raw_preview=raw[:500],
            )
            return self._fallback_chain(findings)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _format_findings(findings: list[dict]) -> str:
        lines: list[str] = []
        for i, f in enumerate(findings, start=1):
            severity = f.get("severity", "unknown")
            title = f.get("title", "Untitled")
            cve_list = ", ".join(f.get("cve", []) or [])
            mitre = ", ".join(f.get("mitre_techniques", []) or [])
            line = f"{i}. [{severity.upper()}] {title}"
            if cve_list:
                line += f" (CVE: {cve_list})"
            if mitre:
                line += f" [MITRE: {mitre}]"
            lines.append(line)
        return "\n".join(lines) if lines else "No findings provided."

    @staticmethod
    def _fallback_chain(findings: list[dict]) -> AttackChain:
        """Return a minimal stub chain when LLM parsing fails."""
        return AttackChain(
            chain_id=str(uuid.uuid4()),
            objective_en="Attack chain generation failed — review findings manually.",
            target_assets=[],
            steps=[
                AttackStep(
                    step=1,
                    tactic="Unknown",
                    technique_id="T0000",
                    technique_name="LLM generation failed",
                    description_en=(
                        "The LLM could not generate a valid attack chain. "
                        f"There are {len(findings)} finding(s) to review manually."
                    ),
                    preconditions=[],
                    tools=[],
                    detection_hints=[],
                )
            ],
            overall_likelihood="low",
            overall_impact="info",
            kill_chain_phases=[],
        )
