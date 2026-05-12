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


@router.get("/{scan_id}/attack-chains/{chain_id}", response_model=AttackChainResponse)
async def get_attack_chain(
    scan_id: uuid.UUID,
    chain_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> AttackChainResponse:
    """Return a single attack chain by ID."""
    stmt = select(AttackChainModel).where(
        AttackChainModel.id == chain_id,
        AttackChainModel.scan_id == scan_id,
    )
    chain = (await db.execute(stmt)).scalar_one_or_none()
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attack chain not found.")
    return _model_to_response(chain)


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


# ---------------------------------------------------------------------------
# GET /{scan_id}/attack-chains/{chain_id}/export.yaml
# ---------------------------------------------------------------------------


@router.get("/{scan_id}/attack-chains/{chain_id}/export.yaml")
async def export_attack_chain_yaml(
    scan_id: uuid.UUID,
    chain_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> Any:
    """Export an attack chain as a YAML file download."""
    from fastapi.responses import Response
    from src.adapters.scenario_yaml import chain_to_yaml

    stmt = select(AttackChainModel).where(
        AttackChainModel.id == chain_id,
        AttackChainModel.scan_id == scan_id,
    )
    chain = (await db.execute(stmt)).scalar_one_or_none()
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attack chain not found.")

    yaml_content = chain_to_yaml(chain)
    filename = f"attack-chain-{chain_id}.yaml"
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# POST /{scan_id}/attack-chains/import
# ---------------------------------------------------------------------------


class ImportChainRequest(BaseModel):
    yaml_content: str


@router.post(
    "/{scan_id}/attack-chains/import",
    response_model=AttackChainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_attack_chain_yaml(
    scan_id: uuid.UUID,
    body: ImportChainRequest,
    current_user: UserDep,
    db: DbDep,
) -> AttackChainResponse:
    """Import an attack chain from YAML into a scan."""
    from src.adapters.scenario_yaml import yaml_to_chain_fields

    await _get_scan_or_404(db, scan_id)

    try:
        fields = yaml_to_chain_fields(body.yaml_content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    model = AttackChainModel(
        id=uuid.uuid4(),
        scan_id=scan_id,
        created_at=_utcnow(),
        **fields,
    )
    db.add(model)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="attack_chain_imported",
        user_id=current_user.id,
        entity="attack_chain",
        entity_id=str(model.id),
        payload={"scan_id": str(scan_id), "steps_count": len(fields["steps"])},
    )
    await db.commit()
    return _model_to_response(model)


# ---------------------------------------------------------------------------
# PUT /{scan_id}/attack-chains/{chain_id}  — update steps from editor
# ---------------------------------------------------------------------------


class UpdateChainRequest(BaseModel):
    steps: list[dict[str, Any]]
    objective_en: str | None = None
    overall_likelihood: str | None = None
    overall_impact: str | None = None


@router.put("/{scan_id}/attack-chains/{chain_id}", response_model=AttackChainResponse)
async def update_attack_chain(
    scan_id: uuid.UUID,
    chain_id: uuid.UUID,
    body: UpdateChainRequest,
    current_user: UserDep,
    db: DbDep,
) -> AttackChainResponse:
    """Update attack chain steps (used by the drag-drop scenario editor)."""
    stmt = select(AttackChainModel).where(
        AttackChainModel.id == chain_id,
        AttackChainModel.scan_id == scan_id,
    )
    chain = (await db.execute(stmt)).scalar_one_or_none()
    if chain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attack chain not found.")

    chain.steps = body.steps
    if body.objective_en is not None:
        chain.objective_en = body.objective_en
    if body.overall_likelihood is not None:
        chain.overall_likelihood = body.overall_likelihood
    if body.overall_impact is not None:
        chain.overall_impact = body.overall_impact

    await db.commit()
    return _model_to_response(chain)


# ---------------------------------------------------------------------------
# GET /{scan_id}/attack-chains/{chain_id}/export.stix  (#30)
# GET /{scan_id}/attack-chains/{chain_id}/export.yaml  (existing, documented)
# GET /{scan_id}/attack-chains/{chain_id}/export.png   (documented — generated client-side)
# ---------------------------------------------------------------------------

import json as _json
from datetime import datetime as _dt_stix, timezone as _tz_stix


@router.get("/{scan_id}/attack-chains/{chain_id}/export.stix")
async def export_chain_stix(
    scan_id: uuid.UUID,
    chain_id: uuid.UUID,
    current_user: UserDep,  # noqa: ARG001
    db: DbDep,
):
    """Export attack chain as STIX 2.1 Bundle with attack-pattern SDOs. (#30)"""
    from fastapi.responses import Response as _Resp

    stmt = select(AttackChainModel).where(
        AttackChainModel.id == chain_id,
        AttackChainModel.scan_id == scan_id,
    )
    chain = (await db.execute(stmt)).scalar_one_or_none()
    if chain is None:
        raise HTTPException(status_code=404, detail="Attack chain not found.")

    now_iso = _dt_stix.now(_tz_stix.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle_id = f"bundle--{uuid.uuid4()}"
    objects = []

    for step in (chain.steps or []):
        ap_id = f"attack-pattern--{uuid.uuid4()}"
        technique_id = step.get("technique_id", "")
        ext_refs = []
        if technique_id:
            ext_refs.append({
                "source_name": "mitre-attack",
                "external_id": technique_id,
                "url": f"https://attack.mitre.org/techniques/{technique_id}/",
            })

        objects.append({
            "type": "attack-pattern",
            "spec_version": "2.1",
            "id": ap_id,
            "created": now_iso,
            "modified": now_iso,
            "name": step.get("technique_name") or step.get("label", f"Step {step.get('step', '?')}"),
            "description": step.get("description_en", ""),
            "kill_chain_phases": [
                {
                    "kill_chain_name": "mitre-attack",
                    "phase_name": (step.get("tactic", "unknown")).lower().replace(" ", "-"),
                }
            ] if step.get("tactic") else [],
            "external_references": ext_refs,
            "x_osint_kind": step.get("kind", "tool"),
            "x_osint_fail_soft": step.get("fail_soft", False),
            "x_osint_tools": step.get("tools", []),
        })

    # Course-of-action for the objective
    if chain.objective_en:
        objects.append({
            "type": "course-of-action",
            "spec_version": "2.1",
            "id": f"course-of-action--{uuid.uuid4()}",
            "created": now_iso,
            "modified": now_iso,
            "name": chain.objective_en,
            "description": f"Attack scenario objective. Likelihood: {chain.overall_likelihood}. Impact: {chain.overall_impact}.",
        })

    bundle = {
        "type": "bundle",
        "id": bundle_id,
        "objects": objects,
    }

    return _Resp(
        content=_json.dumps(bundle, indent=2),
        media_type="application/stix+json",
        headers={"Content-Disposition": f'attachment; filename="chain-{chain_id}.stix.json"'},
    )


# ---------------------------------------------------------------------------
# POST /{scan_id}/attack-chains/import-navigator  (#33 MITRE Navigator JSON)
# ---------------------------------------------------------------------------


class NavigatorImportRequest(BaseModel):
    navigator_json: dict  # raw MITRE Navigator layer JSON


@router.post(
    "/{scan_id}/attack-chains/import-navigator",
    response_model=AttackChainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_from_navigator(
    scan_id: uuid.UUID,
    body: NavigatorImportRequest,
    current_user: UserDep,
    db: DbDep,
) -> AttackChainResponse:
    """Import a MITRE ATT&CK Navigator layer as an attack chain. (#33)

    Accepts Navigator v4 JSON: https://github.com/mitre-attack/attack-navigator
    Each technique in the layer becomes a 'tool' node in the chain.
    """
    await _get_scan_or_404(db, scan_id)

    layer = body.navigator_json
    name = layer.get("name", "Imported from Navigator")
    techniques = layer.get("techniques", [])

    steps = []
    for i, tech in enumerate(techniques, start=1):
        tech_id = tech.get("techniqueID", "")
        tactic = (tech.get("tactic") or "").replace("-", " ").title() if tech.get("tactic") else "Unknown"
        steps.append({
            "id": str(uuid.uuid4())[:8],
            "step": i,
            "kind": "tool",
            "label": tech.get("comment") or tech_id or f"Step {i}",
            "tactic": tactic,
            "technique_id": tech_id,
            "technique_name": tech.get("comment", ""),
            "fail_soft": False,
            "tools": [],
            "preconditions": [],
            "detection_hints": [],
            "config": {
                "score": tech.get("score"),
                "color": tech.get("color", ""),
                "metadata": tech.get("metadata", []),
            },
        })

    if not steps:
        raise HTTPException(status_code=422, detail="Navigator layer contains no techniques.")

    model = AttackChainModel(
        id=uuid.uuid4(),
        scan_id=scan_id,
        objective_en=name,
        steps=steps,
        overall_likelihood="medium",
        overall_impact="high",
        created_at=_utcnow(),
    )
    db.add(model)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="attack_chain_imported_navigator",
        user_id=current_user.id,
        entity="attack_chain",
        entity_id=str(model.id),
        payload={"scan_id": str(scan_id), "steps": len(steps), "layer_name": name},
    )
    await db.commit()
    return _model_to_response(model)
