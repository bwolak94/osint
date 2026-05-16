"""Investigation report generator — produces HTML/JSON reports for investigations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.dependencies import get_db

router = APIRouter(prefix="/investigations", tags=["reports"])


class ReportOptions(BaseModel):
    format: str = "html"  # html / json / markdown
    include_raw_findings: bool = False
    include_graph_data: bool = False


def _generate_html_report(
    investigation: Any,
    scan_results: list[Any],
    risk_score: dict[str, Any] | None = None,
) -> str:
    """Generate a self-contained HTML report for an investigation."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = getattr(investigation, "title", "OSINT Investigation Report")
    inv_id = str(investigation.id)
    created = getattr(investigation, "created_at", "")

    # Aggregate findings
    all_findings: list[dict[str, Any]] = []
    scanner_summaries: list[dict[str, Any]] = []
    for sr in scan_results:
        raw = sr.raw_output or {}
        findings = raw.get("findings", [])
        all_findings.extend(findings)
        scanner_summaries.append({
            "scanner": sr.scanner_name,
            "total_findings": len(findings),
            "severity_counts": {
                sev: sum(1 for f in findings if f.get("severity") == sev)
                for sev in ("critical", "high", "medium", "low", "info")
            },
        })

    # Count severities
    sev_counts: dict[str, int] = {}
    for f in all_findings:
        s = f.get("severity", "info")
        sev_counts[s] = sev_counts.get(s, 0) + 1

    risk_level = (risk_score or {}).get("risk_level", "UNKNOWN")
    risk_val = (risk_score or {}).get("score", "N/A")

    sev_colors = {
        "critical": "#dc2626",
        "high": "#ea580c",
        "medium": "#ca8a04",
        "low": "#16a34a",
        "info": "#2563eb",
    }

    findings_html = ""
    for f in all_findings[:50]:
        sev = f.get("severity", "info")
        color = sev_colors.get(sev, "#6b7280")
        findings_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #1e293b;">
                <span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">
                    {sev.upper()}
                </span>
            </td>
            <td style="padding:8px;border-bottom:1px solid #1e293b;color:#94a3b8;">{f.get("source","")}</td>
            <td style="padding:8px;border-bottom:1px solid #1e293b;color:#e2e8f0;">{f.get("description","")[:120]}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — OSINT Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px; }}
  .header {{ border-bottom: 2px solid #1e3a5f; padding-bottom: 24px; margin-bottom: 32px; }}
  .header h1 {{ font-size: 28px; font-weight: 700; color: #38bdf8; }}
  .header .meta {{ color: #64748b; font-size: 13px; margin-top: 8px; }}
  .risk-badge {{ display: inline-block; padding: 6px 20px; border-radius: 6px;
                 font-weight: 700; font-size: 16px; margin: 16px 0; }}
  .risk-CRITICAL {{ background: #7f1d1d; color: #fca5a5; }}
  .risk-HIGH {{ background: #7c2d12; color: #fdba74; }}
  .risk-MEDIUM {{ background: #713f12; color: #fde68a; }}
  .risk-LOW {{ background: #14532d; color: #86efac; }}
  .risk-UNKNOWN {{ background: #1e293b; color: #94a3b8; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 24px 0; }}
  .stat-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; }}
  .stat-card .value {{ font-size: 32px; font-weight: 700; color: #38bdf8; }}
  .stat-card .label {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
  .section {{ margin: 32px 0; }}
  .section h2 {{ font-size: 18px; font-weight: 600; color: #94a3b8; margin-bottom: 16px;
                 border-left: 3px solid #38bdf8; padding-left: 12px; }}
  table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
  th {{ padding: 12px 8px; text-align: left; background: #0f172a; color: #64748b; font-size: 12px;
        font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
  .footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #1e293b;
             color: #475569; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>OSINT Investigation Report</h1>
    <div class="meta">
      Investigation: {inv_id} &nbsp;|&nbsp; Generated: {now} &nbsp;|&nbsp; Created: {created}
    </div>
    <h2 style="margin-top:12px;font-size:20px;color:#e2e8f0;">{title}</h2>
    <div class="risk-badge risk-{risk_level}">
      Risk Level: {risk_level} &nbsp; ({risk_val}/100)
    </div>
  </div>

  <div class="grid">
    <div class="stat-card">
      <div class="value">{len(all_findings)}</div>
      <div class="label">Total Findings</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color:#dc2626;">{sev_counts.get("critical", 0)}</div>
      <div class="label">Critical</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color:#ea580c;">{sev_counts.get("high", 0)}</div>
      <div class="label">High</div>
    </div>
    <div class="stat-card">
      <div class="value" style="color:#ca8a04;">{sev_counts.get("medium", 0)}</div>
      <div class="label">Medium</div>
    </div>
    <div class="stat-card">
      <div class="value">{len(scan_results)}</div>
      <div class="label">Scanners Run</div>
    </div>
  </div>

  <div class="section">
    <h2>Findings</h2>
    <table>
      <thead>
        <tr>
          <th>Severity</th>
          <th>Source</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {findings_html if findings_html else '<tr><td colspan="3" style="padding:16px;color:#64748b;text-align:center;">No findings</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="footer">
    Generated by OSINT Platform &nbsp;|&nbsp; {now} &nbsp;|&nbsp;
    This report is confidential and for authorized use only.
  </div>
</div>
</body>
</html>"""


@router.get("/{investigation_id}/report")
async def generate_report(
    investigation_id: str,
    format: str = "html",
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Response:
    """Generate and download an investigation report (HTML or JSON)."""
    from sqlalchemy import select
    from src.adapters.db.models import InvestigationModel, ScanResultModel

    inv = await db.get(InvestigationModel, investigation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    if str(inv.owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(
        select(ScanResultModel).where(ScanResultModel.investigation_id == investigation_id)
    )
    scan_results = result.scalars().all()

    if format == "json":
        all_findings: list[dict[str, Any]] = []
        for sr in scan_results:
            raw = sr.raw_output or {}
            all_findings.extend(raw.get("findings", []))

        report_data = {
            "investigation_id": investigation_id,
            "title": inv.title,
            "created_at": str(inv.created_at),
            "total_findings": len(all_findings),
            "scanners_run": len(scan_results),
            "findings": all_findings,
        }
        return Response(
            content=json.dumps(report_data, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="report-{investigation_id}.json"'},
        )

    # Default: HTML
    html = _generate_html_report(inv, scan_results)
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="report-{investigation_id}.html"'},
    )
