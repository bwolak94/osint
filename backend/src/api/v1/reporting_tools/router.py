"""Reporting Tools API — OSCP report generator, password policy auditor."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api.v1.auth.dependencies import get_current_user
from src.adapters.scanners.pentest.oscp_report_runner import OscpReportRunner
from src.adapters.scanners.pentest.password_policy_runner import PasswordPolicyRunner
import structlog

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/reporting-tools", tags=["reporting-tools"])


class RunRequest(BaseModel):
    target: str
    options: dict[str, Any] | None = None


def _to_result(result) -> dict:
    return {
        "tool": result.tool,
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "findings": [f.__dict__ for f in result.findings],
        "error": result.error,
        "metadata": result.metadata or {},
    }


@router.post("/oscp-report")
async def generate_oscp_report(req: RunRequest, _=Depends(get_current_user)):
    result = await OscpReportRunner().run(req.target, req.options)
    return _to_result(result)


@router.post("/password-policy")
async def audit_password_policy(req: RunRequest, _=Depends(get_current_user)):
    result = await PasswordPolicyRunner().run(req.target, req.options)
    return _to_result(result)
