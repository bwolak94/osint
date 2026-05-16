"""Multi-format data export — export investigation findings as CSV, JSONL, or MISP.

GET /api/v1/investigations/{id}/export?format=csv|jsonl|misp|stix
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_VALID_FORMATS = ("csv", "jsonl", "misp", "markdown")


@router.get("/investigations/{investigation_id}/export", tags=["export"])
async def export_investigation(
    investigation_id: str,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> Response:
    """Export investigation findings in various formats."""
    if format not in _VALID_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format '{format}'. Valid formats: {', '.join(_VALID_FORMATS)}",
        )

    inv_result = await db.execute(
        select(InvestigationModel).where(InvestigationModel.id == investigation_id)
    )
    investigation = inv_result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Investigation not found")

    sr_result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == investigation_id
        ).limit(500)
    )
    scan_results = sr_result.scalars().all()

    # Flatten all findings
    all_findings: list[dict[str, Any]] = []
    for sr in scan_results:
        for f in (sr.raw_data or {}).get("findings", []):
            all_findings.append({
                "scanner": sr.scanner_name,
                "scanned_at": sr.created_at.isoformat() if sr.created_at else "",
                **{k: v for k, v in f.items() if not isinstance(v, (dict, list))},
            })

    title = getattr(investigation, "title", investigation_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title)[:40]

    if format == "csv":
        return _export_csv(all_findings, f"{safe_title}_{ts}.csv")
    elif format == "jsonl":
        return _export_jsonl(all_findings, f"{safe_title}_{ts}.jsonl")
    elif format == "misp":
        return _export_misp(all_findings, title, investigation_id, f"{safe_title}_{ts}_misp.json")
    else:  # markdown
        return _export_markdown(all_findings, title, f"{safe_title}_{ts}.md")


def _export_csv(findings: list[dict[str, Any]], filename: str) -> Response:
    if not findings:
        return Response(content="scanner,type,severity,description\n",
                        media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})

    fields = ["scanner", "type", "severity", "source", "description", "scanned_at"]
    # Add any extra scalar fields found
    extra = sorted(set(k for f in findings for k in f if k not in fields
                        and isinstance(f[k], (str, int, float, bool, type(None)))))

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields + extra, extrasaction="ignore",
                             lineterminator="\n")
    writer.writeheader()
    for f in findings:
        writer.writerow({k: str(f.get(k, "")) for k in fields + extra})

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _export_jsonl(findings: list[dict[str, Any]], filename: str) -> Response:
    lines = "\n".join(json.dumps(f, default=str) for f in findings)
    return Response(
        content=lines,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _export_misp(findings: list[dict[str, Any]], title: str,
                  inv_id: str, filename: str) -> Response:
    """Export as MISP event JSON format."""
    attributes = []
    for f in findings:
        for field in ("ip", "domain", "email", "url", "md5", "sha256", "sha1"):
            val = f.get(field)
            if val and isinstance(val, str):
                attributes.append({
                    "category": "Network activity" if field in ("ip", "domain", "url") else "Payload delivery",
                    "type": {"ip": "ip-dst", "domain": "domain", "email": "email-dst",
                              "url": "url", "md5": "md5", "sha256": "sha256",
                              "sha1": "sha1"}.get(field, field),
                    "value": val,
                    "comment": f.get("description", "")[:200],
                    "to_ids": True,
                })

    misp_event = {
        "Event": {
            "info": title,
            "uuid": inv_id,
            "Attribute": attributes[:500],
            "Tag": [{"name": "tlp:white"}, {"name": "osint:source-type=\"review-blog\""}],
            "date": datetime.now(timezone.utc).date().isoformat(),
            "distribution": 0,
            "threat_level_id": 2,
            "analysis": 1,
        }
    }
    return Response(
        content=json.dumps(misp_event, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _export_markdown(findings: list[dict[str, Any]], title: str, filename: str) -> Response:
    lines = [f"# Investigation: {title}", "", f"**Total findings:** {len(findings)}", ""]
    severity_order = ["critical", "high", "medium", "low", "info"]
    by_severity: dict[str, list[dict[str, Any]]] = {s: [] for s in severity_order}
    for f in findings:
        sev = f.get("severity", "info").lower()
        by_severity.setdefault(sev, []).append(f)

    for sev in severity_order:
        sev_findings = by_severity.get(sev, [])
        if sev_findings:
            lines.append(f"## {sev.upper()} ({len(sev_findings)})")
            lines.append("")
            for f in sev_findings[:20]:
                desc = f.get("description", "")
                scanner = f.get("scanner", "")
                lines.append(f"- **[{scanner}]** {desc}")
            if len(sev_findings) > 20:
                lines.append(f"  _...and {len(sev_findings) - 20} more_")
            lines.append("")

    return Response(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
