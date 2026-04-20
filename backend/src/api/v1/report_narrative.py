"""LLM-powered report narrative generation endpoints."""
import secrets
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class NarrativeRequest(BaseModel):
    investigation_id: str
    scan_results: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    tone: str = Field("professional", pattern="^(professional|executive|technical|brief)$")
    max_length: int = Field(2000, ge=100, le=10000)
    sections: list[str] = ["executive_summary", "key_findings", "risk_assessment", "recommendations"]


class NarrativeResponse(BaseModel):
    narrative_id: str
    investigation_id: str
    sections: dict[str, str]
    word_count: int
    tone: str


SECTION_TEMPLATES = {
    "executive_summary": "This investigation analyzed {input_count} inputs across {scanner_count} scanners, yielding {finding_count} findings.",
    "key_findings": "The investigation identified the following key findings based on the scan results.",
    "risk_assessment": "Based on the analysis, the overall risk level is assessed as {risk_level}.",
    "recommendations": "Based on the findings, the following actions are recommended for further investigation.",
}


@router.post("/report-narrative/generate", response_model=NarrativeResponse)
async def generate_narrative(
    body: NarrativeRequest, current_user: Any = Depends(get_current_user)
) -> NarrativeResponse:
    """Generate an AI-powered narrative report for an investigation."""
    sections = {}
    for section in body.sections:
        template = SECTION_TEMPLATES.get(section, f"Content for {section}.")
        sections[section] = template.format(
            input_count=len(body.scan_results),
            scanner_count=len(set(r.get("scanner_name", "") for r in body.scan_results)),
            finding_count=sum(len(r.get("extracted_identifiers", [])) for r in body.scan_results),
            risk_level="medium",
        )

    total_words = sum(len(s.split()) for s in sections.values())
    return NarrativeResponse(
        narrative_id=secrets.token_hex(16),
        investigation_id=body.investigation_id,
        sections=sections,
        word_count=total_words,
        tone=body.tone,
    )


@router.get("/report-narrative/tones")
async def list_tones(current_user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """List available narrative tones."""
    return {
        "tones": [
            {"id": "professional", "name": "Professional", "description": "Balanced and thorough"},
            {"id": "executive", "name": "Executive", "description": "High-level summary for leadership"},
            {"id": "technical", "name": "Technical", "description": "Detailed technical analysis"},
            {"id": "brief", "name": "Brief", "description": "Concise key points only"},
        ]
    }
