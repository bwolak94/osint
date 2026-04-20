"""Custom report builder endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

DEFAULT_SECTIONS = [
    {"type": "header", "label": "Report Header", "config": {"show_logo": True, "show_date": True}},
    {"type": "executive_summary", "label": "Executive Summary", "config": {"max_length": 500}},
    {"type": "findings_table", "label": "Key Findings", "config": {"columns": ["scanner", "finding", "severity"]}},
    {"type": "identity_cards", "label": "Resolved Identities", "config": {"show_confidence": True}},
    {"type": "scan_results", "label": "Detailed Scan Results", "config": {"group_by": "scanner"}},
    {"type": "graph_snapshot", "label": "Relationship Graph", "config": {"layout": "force-directed"}},
    {"type": "timeline", "label": "Investigation Timeline", "config": {}},
    {"type": "risk_assessment", "label": "Risk Assessment", "config": {"show_score": True}},
    {"type": "recommendations", "label": "Recommendations", "config": {}},
    {"type": "appendix", "label": "Raw Data Appendix", "config": {"include_raw": False}},
]


class ReportTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    sections: list[dict] = []
    branding: dict = {}


class ReportTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    sections: list[dict]
    branding: dict
    is_default: bool
    created_at: str


class ReportTemplateListResponse(BaseModel):
    templates: list[ReportTemplateResponse]
    total: int


class ReportBuildRequest(BaseModel):
    investigation_id: str
    template_id: str | None = None
    sections: list[dict] | None = None
    format: str = Field("html", pattern="^(pdf|html|json|csv)$")
    title: str = "Investigation Report"


class ReportBuildResponse(BaseModel):
    report_id: str
    status: str
    format: str
    download_url: str | None


@router.get("/report-builder/sections")
async def list_available_sections(
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """List all available report sections."""
    return {"sections": DEFAULT_SECTIONS}


@router.get("/report-builder/templates", response_model=ReportTemplateListResponse)
async def list_report_templates(
    current_user: Any = Depends(get_current_user),
) -> ReportTemplateListResponse:
    """List custom report templates."""
    return ReportTemplateListResponse(templates=[], total=0)


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
        description=body.description,
        sections=body.sections or DEFAULT_SECTIONS,
        branding=body.branding,
        is_default=False,
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

    return ReportBuildResponse(
        report_id=report_id,
        status="building",
        format=body.format,
        download_url=None,  # Will be populated when build completes
    )
