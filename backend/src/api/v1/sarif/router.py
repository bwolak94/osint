"""SARIF and DOCX export endpoints for pentest scan reports.

Endpoints:
  GET /scans/{scan_id}/export/sarif — SARIF 2.1.0 JSON export
  GET /scans/{scan_id}/export/docx  — DOCX report download
  GET /scans/{scan_id}/export/html  — HTML report download
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_models import EngagementModel, PentestFindingModel, PentestScanModel
from src.adapters.reporting.docx_generator import DocxGenerator
from src.adapters.reporting.sarif_generator import SarifGenerator
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter(tags=["pentest-export"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(require_pentester)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_scan_or_404(
    scan_id: uuid.UUID, db: AsyncSession
) -> PentestScanModel:
    """Fetch a scan by ID or raise 404."""
    stmt = select(PentestScanModel).where(PentestScanModel.id == scan_id)
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return scan


async def _get_findings(
    scan_id: uuid.UUID, db: AsyncSession
) -> list[PentestFindingModel]:
    """Fetch all findings for a scan ordered by severity."""
    stmt = (
        select(PentestFindingModel)
        .where(PentestFindingModel.scan_id == scan_id)
        .order_by(PentestFindingModel.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _get_engagement(
    engagement_id: uuid.UUID, db: AsyncSession
) -> EngagementModel | None:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}/export/sarif
# ---------------------------------------------------------------------------


@router.get("/{scan_id}/export/sarif")
async def export_sarif(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> Response:
    """Export scan findings as SARIF 2.1.0 JSON.

    Returns a downloadable ``.sarif`` file suitable for GitHub Advanced Security,
    Azure DevOps, or any SARIF-compatible viewer.
    """
    scan = await _get_scan_or_404(scan_id, db)
    findings = await _get_findings(scan_id, db)

    generator = SarifGenerator()
    sarif_json = generator.to_json(findings, scan_id=str(scan_id))

    await log.ainfo("sarif_export", scan_id=str(scan_id), finding_count=len(findings))

    return Response(
        content=sarif_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="pentest-{scan_id}.sarif"',
            "X-Finding-Count": str(len(findings)),
        },
    )


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}/export/docx
# ---------------------------------------------------------------------------


@router.get("/{scan_id}/export/docx")
async def export_docx(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> Response:
    """Export scan findings as a DOCX report.

    Returns a professional Word document with cover page, executive summary,
    findings, and appendix. Falls back to HTML if python-docx is not installed.
    """
    scan = await _get_scan_or_404(scan_id, db)
    findings = await _get_findings(scan_id, db)
    engagement = await _get_engagement(scan.engagement_id, db)

    generator = DocxGenerator()
    report_bytes, mime_type = generator.generate(scan, findings, engagement)

    await log.ainfo("docx_export", scan_id=str(scan_id), finding_count=len(findings))

    if mime_type == "text/html":
        # Fallback HTML — serve as HTML download
        return Response(
            content=report_bytes,
            media_type="text/html",
            headers={
                "Content-Disposition": f'attachment; filename="pentest-{scan_id}.html"',
            },
        )

    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="pentest-{scan_id}.docx"',
            "X-Finding-Count": str(len(findings)),
        },
    )


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}/export/html
# ---------------------------------------------------------------------------


@router.get("/{scan_id}/export/html")
async def export_html(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> Response:
    """Export scan findings as a styled HTML report.

    Always returns HTML regardless of python-docx availability — useful for
    quick in-browser preview or email distribution.
    """
    scan = await _get_scan_or_404(scan_id, db)
    findings = await _get_findings(scan_id, db)
    engagement = await _get_engagement(scan.engagement_id, db)

    generator = DocxGenerator()
    # Force HTML generation by calling the internal method directly
    html_content = generator._generate_html(scan, findings, engagement)

    await log.ainfo("html_export", scan_id=str(scan_id), finding_count=len(findings))

    return Response(
        content=html_content.encode("utf-8"),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="pentest-{scan_id}.html"',
            "X-Finding-Count": str(len(findings)),
        },
    )
