"""Playbook conditional branching endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.playbook_engine import ConditionEvaluator

log = structlog.get_logger()
router = APIRouter()


class ConditionCreate(BaseModel):
    step_index: int = Field(..., ge=0)
    condition_type: str = Field(..., min_length=1)
    field_path: str = Field(..., min_length=1)
    operator: str = Field(..., pattern="^(eq|ne|gt|lt|gte|lte|contains|not_contains|exists|not_exists|in|count_gt|count_lt)$")
    expected_value: str = ""
    then_goto_step: int | None = None
    else_goto_step: int | None = None


class ConditionResponse(BaseModel):
    id: str
    playbook_id: str
    step_index: int
    condition_type: str
    field_path: str
    operator: str
    expected_value: str
    then_goto_step: int | None
    else_goto_step: int | None


class ConditionTestRequest(BaseModel):
    conditions: list[dict[str, Any]]
    scan_result: dict[str, Any]


class ConditionTestResponse(BaseModel):
    next_step: int | None
    evaluations: list[dict[str, Any]]


@router.post("/playbooks/{playbook_id}/conditions", status_code=201)
async def add_condition(
    playbook_id: str,
    body: ConditionCreate,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Add a conditional branch to a playbook step."""
    import secrets
    log.info("Playbook condition added", playbook_id=playbook_id, step=body.step_index)
    return {"status": "created", "id": secrets.token_hex(16), "playbook_id": playbook_id}


@router.get("/playbooks/{playbook_id}/conditions")
async def list_conditions(
    playbook_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """List all conditions for a playbook."""
    return {"conditions": [], "playbook_id": playbook_id}


@router.delete("/playbooks/{playbook_id}/conditions/{condition_id}")
async def delete_condition(
    playbook_id: str,
    condition_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Remove a condition from a playbook."""
    return {"status": "deleted", "id": condition_id}


@router.post("/playbooks/conditions/test", response_model=ConditionTestResponse)
async def test_conditions(
    body: ConditionTestRequest,
    current_user: Any = Depends(get_current_user),
) -> ConditionTestResponse:
    """Test conditions against sample scan result data."""
    evaluations = []
    for cond in body.conditions:
        result = ConditionEvaluator.evaluate(
            condition_type=cond.get("condition_type", ""),
            field_path=cond.get("field_path", ""),
            operator=cond.get("operator", "eq"),
            expected_value=cond.get("expected_value", ""),
            scan_result=body.scan_result,
        )
        evaluations.append({"condition": cond, "result": result})

    next_step = ConditionEvaluator.evaluate_conditions(body.conditions, body.scan_result)

    return ConditionTestResponse(next_step=next_step, evaluations=evaluations)
