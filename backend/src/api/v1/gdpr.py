"""GDPR Article 15 Data Subject Request Automation router."""

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


class GdprSubjectRequest(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    include_breach_check: bool = True
    include_social_scan: bool = True
    include_paste_check: bool = True
    include_stealer_logs: bool = True
    requester_reference: Optional[str] = None


class ExposureSource(BaseModel):
    source_type: str  # breach, social, paste, stealer, public_record
    source_name: str
    found_data: list[str]  # list of data fields found
    severity: str  # low, medium, high, critical
    date_found: Optional[str]


class GdprReport(BaseModel):
    report_id: str
    status: str  # queued, running, completed, failed
    subject_name: str
    subject_email: str
    created_at: str
    completed_at: Optional[str]
    exposure_sources: list[ExposureSource]
    total_exposures: int
    risk_score: str  # low, medium, high, critical
    summary: str
    recommended_actions: list[str]
    requester_reference: Optional[str]


MOCK_REPORTS: dict[str, GdprReport] = {}


@router.post("/subject-requests", response_model=GdprReport)
async def create_subject_request(
    request: GdprSubjectRequest, background_tasks: BackgroundTasks
) -> GdprReport:
    """Create a new GDPR data subject exposure report."""
    report_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()

    exposure_sources: list[ExposureSource] = []

    if request.include_breach_check:
        exposure_sources.append(
            ExposureSource(
                source_type="breach",
                source_name="HaveIBeenPwned",
                found_data=["email", "password_hash", "username"],
                severity="high",
                date_found="2023-03",
            )
        )
        exposure_sources.append(
            ExposureSource(
                source_type="breach",
                source_name="LinkedIn 2021",
                found_data=["email", "name", "phone", "employer"],
                severity="medium",
                date_found="2021-06",
            )
        )

    if request.include_paste_check:
        exposure_sources.append(
            ExposureSource(
                source_type="paste",
                source_name="Pastebin",
                found_data=["email", "password_plaintext"],
                severity="critical",
                date_found="2024-01",
            )
        )

    if request.include_social_scan:
        exposure_sources.append(
            ExposureSource(
                source_type="social",
                source_name="Twitter/X",
                found_data=["username", "bio", "location", "profile_photo"],
                severity="low",
                date_found=None,
            )
        )

    if request.include_stealer_logs:
        exposure_sources.append(
            ExposureSource(
                source_type="stealer",
                source_name="RedLine Stealer DB",
                found_data=["email", "password_plaintext", "browser_cookies"],
                severity="critical",
                date_found="2024-02",
            )
        )

    total_exposures = len(exposure_sources)

    if total_exposures == 0:
        risk_score = "low"
    elif any(s.severity == "critical" for s in exposure_sources):
        risk_score = "critical"
    elif any(s.severity == "high" for s in exposure_sources):
        risk_score = "high"
    elif any(s.severity == "medium" for s in exposure_sources):
        risk_score = "medium"
    else:
        risk_score = "low"

    breach_count = sum(1 for s in exposure_sources if s.source_type == "breach")
    paste_count = sum(1 for s in exposure_sources if s.source_type == "paste")
    stealer_count = sum(1 for s in exposure_sources if s.source_type == "stealer")

    summary_parts: list[str] = []
    if breach_count:
        summary_parts.append(f"{breach_count} data breach(es)")
    if paste_count:
        summary_parts.append(f"{paste_count} paste site exposure(s)")
    if stealer_count:
        summary_parts.append(f"{stealer_count} stealer log entry(s)")

    if summary_parts:
        summary = (
            f"Subject {request.full_name} ({request.email}) was found in "
            + ", ".join(summary_parts)
            + ". Credentials may be compromised."
        )
    else:
        summary = (
            f"No significant exposures found for {request.full_name} ({request.email}) "
            "based on selected scan modules."
        )

    recommended_actions: list[str] = []
    if risk_score in ("critical", "high"):
        recommended_actions.extend(
            [
                "Immediately change passwords for all affected accounts",
                "Enable two-factor authentication on all services",
                "Monitor credit reports for identity theft indicators",
                "Request data deletion from breach notification databases",
            ]
        )
    if stealer_count:
        recommended_actions.append(
            "Revoke all active browser sessions and clear saved credentials"
        )
    if paste_count:
        recommended_actions.append(
            "Notify relevant service providers about plaintext credential exposure"
        )
    if not recommended_actions:
        recommended_actions.append(
            "Continue monitoring for new exposures on a quarterly basis"
        )

    report = GdprReport(
        report_id=report_id,
        status="completed",
        subject_name=request.full_name,
        subject_email=request.email,
        created_at=now,
        completed_at=now,
        exposure_sources=exposure_sources,
        total_exposures=total_exposures,
        risk_score=risk_score,
        summary=summary,
        recommended_actions=recommended_actions,
        requester_reference=request.requester_reference,
    )

    MOCK_REPORTS[report_id] = report
    return report


@router.get("/subject-requests", response_model=list[GdprReport])
async def list_subject_requests() -> list[GdprReport]:
    """List all GDPR subject request reports."""
    return list(MOCK_REPORTS.values())


@router.get("/subject-requests/{report_id}", response_model=GdprReport)
async def get_subject_request(report_id: str) -> GdprReport:
    """Retrieve a specific GDPR subject request report by ID."""
    if report_id not in MOCK_REPORTS:
        raise HTTPException(status_code=404, detail="Report not found")
    return MOCK_REPORTS[report_id]
