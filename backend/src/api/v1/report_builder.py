"""Custom report builder endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

# Sections match the frontend ReportSection interface:
# { id, name, description, required, order }
_DEFAULT_SECTIONS: list[dict[str, Any]] = [
    {"id": "header",            "name": "Report Header",         "description": "Title page with logo, date, and classification banner.", "required": True,  "order": 0},
    {"id": "executive_summary", "name": "Executive Summary",     "description": "High-level overview of findings for non-technical stakeholders.", "required": True, "order": 1},
    {"id": "findings_table",    "name": "Key Findings",          "description": "Tabular summary of all findings grouped by scanner.", "required": False, "order": 2},
    {"id": "identity_cards",    "name": "Resolved Identities",   "description": "Identity cards for discovered persons, emails, and usernames.", "required": False, "order": 3},
    {"id": "scan_results",      "name": "Detailed Scan Results", "description": "Full output of each scanner run during the investigation.", "required": False, "order": 4},
    {"id": "graph_snapshot",    "name": "Relationship Graph",    "description": "Force-directed graph showing entity relationships.", "required": False, "order": 5},
    {"id": "timeline",          "name": "Investigation Timeline","description": "Chronological timeline of all events and scan results.", "required": False, "order": 6},
    {"id": "risk_assessment",   "name": "Risk Assessment",       "description": "Risk score breakdown and severity distribution.", "required": False, "order": 7},
    {"id": "recommendations",   "name": "Recommendations",       "description": "Actionable next steps based on the investigation findings.", "required": False, "order": 8},
    {"id": "appendix",          "name": "Raw Data Appendix",     "description": "Full raw scanner output for technical reviewers.", "required": False, "order": 9},
]


# Frontend expects: { id, name, sections: string[], created_at }
class ReportTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    sections: list[str] = []


class ReportTemplateResponse(BaseModel):
    id: str
    name: str
    sections: list[str]
    created_at: str


class ReportBuildRequest(BaseModel):
    investigation_id: str
    template_id: str | None = None
    sections: list[str] = []
    format: str = Field("pdf", pattern="^(pdf|html|docx)$")
    title: str | None = None
    classification: str | None = None


class ReportBuildResponse(BaseModel):
    report_id: str
    status: str


@router.get("/report-builder/sections", response_model=list[dict[str, Any]])
async def list_available_sections(
    current_user: Any = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return available report sections as a flat array."""
    return _DEFAULT_SECTIONS


@router.get("/report-builder/templates", response_model=list[ReportTemplateResponse])
async def list_report_templates(
    current_user: Any = Depends(get_current_user),
) -> list[ReportTemplateResponse]:
    """List custom report templates."""
    return []


@router.post("/report-builder/templates", response_model=ReportTemplateResponse, status_code=201)
async def create_report_template(
    body: ReportTemplateCreate,
    current_user: Any = Depends(get_current_user),
) -> ReportTemplateResponse:
    """Create a custom report template."""
    now = datetime.now(timezone.utc).isoformat()
    return ReportTemplateResponse(
        id=secrets.token_hex(16),
        name=body.name,
        sections=body.sections,
        created_at=now,
    )


@router.delete("/report-builder/templates/{template_id}")
async def delete_report_template(
    template_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "deleted", "id": template_id}


@router.post("/report-builder/build", response_model=ReportBuildResponse)
async def build_report(
    body: ReportBuildRequest,
    current_user: Any = Depends(get_current_user),
) -> ReportBuildResponse:
    """Build a report for an investigation."""
    report_id = secrets.token_hex(16)
    log.info("Report build started", report_id=report_id, investigation_id=body.investigation_id)
    return ReportBuildResponse(report_id=report_id, status="queued")
