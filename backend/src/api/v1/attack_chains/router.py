"""Attack chain API — LLM-generated MITRE ATT&CK kill chains for pentest scans.

Endpoints (mounted under /api/v1/scans):
  POST /{scan_id}/attack-chains/generate  — trigger LLM chain generation, persist to DB
  GET  /{scan_id}/attack-chains           — list all chains for a scan
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.ai.attack_chain_service import AttackChainService
from src.adapters.ai.pentest_llm_service import PentestLLMService
from src.adapters.audit.pentest_actions import PentestAction
from src.adapters.audit.pentest_audit_service import AuditService
from src.adapters.db.pentest_models import (
    AttackChainModel,
    PentestFindingModel,
    PentestScanModel,
)
from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["pentest-attack-chains"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(require_pentester)]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AttackStepResponse(BaseModel):
    step: int
    tactic: str
    technique_id: str
    technique_name: str
    sub_technique_id: str | None
    description_en: str
    preconditions: list[str]
    tools: list[str]
    detection_hints: list[str]


class AttackChainResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    chain_id: str
    objective_en: str | None
    target_assets: list[str]
    steps: list[AttackStepResponse]
    overall_likelihood: str | None
    overall_impact: str | None
    kill_chain_phases: list[str]
    generated_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _model_to_response(m: AttackChainModel) -> AttackChainResponse:
    raw_steps: list[dict[str, Any]] = m.steps or []
    steps = [
        AttackStepResponse(
            step=s.get("step", 0),
            tactic=s.get("tactic", ""),
            technique_id=s.get("technique_id", ""),
            technique_name=s.get("technique_name", ""),
            sub_technique_id=s.get("sub_technique_id"),
            description_en=s.get("description_en", ""),
            preconditions=s.get("preconditions", []),
            tools=s.get("tools", []),
            detection_hints=s.get("detection_hints", []),
        )
        for s in raw_steps
    ]
    return AttackChainResponse(
        id=m.id,
        scan_id=m.scan_id,
        chain_id=str(m.id),
        objective_en=m.objective_en,
        target_assets=[],
        steps=steps,
        overall_likelihood=m.overall_likelihood,
        overall_impact=m.overall_impact,
        kill_chain_phases=[],
        generated_by=m.generated_by,
        created_at=m.created_at,
    )


async def _get_scan_or_404(db: AsyncSession, scan_id: uuid.UUID) -> PentestScanModel:
    stmt = select(PentestScanModel).where(PentestScanModel.id == scan_id)
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return scan


# ---------------------------------------------------------------------------
# POST /{scan_id}/attack-chains/generate
# ---------------------------------------------------------------------------


@router.post(
    "/{scan_id}/attack-chains/generate",
    response_model=AttackChainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_attack_chain(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> AttackChainResponse:
    """Trigger LLM-based attack chain generation for the scan's confirmed findings.

    Fetches all findings for the scan, calls the AttackChainService, persists
    the result, and writes an audit log entry.
    """
    scan = await _get_scan_or_404(db, scan_id)

    # Fetch findings for this scan
    findings_stmt = (
        select(PentestFindingModel)
        .where(PentestFindingModel.scan_id == scan_id)
        .order_by(PentestFindingModel.created_at.asc())
    )
    findings_rows = (await db.execute(findings_stmt)).scalars().all()

    findings_dicts = [
        {
            "title": f.title,
            "severity": f.severity,
            "cve": f.cve or [],
            "mitre_techniques": f.mitre_techniques or [],
            "description": f.description,
        }
        for f in findings_rows
    ]

    llm_service = PentestLLMService()
    chain_service = AttackChainService(llm_service)

    engagement_context = (
        f"Pentest engagement scan {scan_id}. "
        f"Profile: {scan.profile}."
    )

    chain = await chain_service.generate_chain(
        findings=findings_dicts,
        engagement_context=engagement_context,
    )

    # Persist to DB
    model = AttackChainModel(
        id=uuid.uuid4(),
        scan_id=scan_id,
        objective_en=chain.objective_en,
        steps=[s.model_dump() for s in chain.steps],
        overall_likelihood=chain.overall_likelihood,
        overall_impact=chain.overall_impact,
        generated_by=llm_service._planner_model,
        created_at=_utcnow(),
    )
    db.add(model)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.ATTACK_CHAIN_GENERATED,
        user_id=current_user.id,
        entity="attack_chain",
        entity_id=str(model.id),
        payload={
            "scan_id": str(scan_id),
            "steps_count": len(chain.steps),
            "overall_impact": chain.overall_impact,
        },
    )

    await log.ainfo(
        "attack_chain_generated",
        scan_id=str(scan_id),
        chain_id=str(model.id),
        steps=len(chain.steps),
    )

    return _model_to_response(model)


# ---------------------------------------------------------------------------
# GET /{scan_id}/attack-chains
# ---------------------------------------------------------------------------


@router.get("/{scan_id}/attack-chains", response_model=list[AttackChainResponse])
async def list_attack_chains(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> list[AttackChainResponse]:
    """List all attack chains generated for a scan, newest first."""
    await _get_scan_or_404(db, scan_id)

    stmt = (
        select(AttackChainModel)
        .where(AttackChainModel.scan_id == scan_id)
        .order_by(AttackChainModel.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_model_to_response(r) for r in rows]
