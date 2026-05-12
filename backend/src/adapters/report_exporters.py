"""Report export adapters — HTML, CSV, STIX 2.1.

Each function accepts a list of findings (dicts) and returns bytes.
SARIF and PDF exporters live in adjacent files.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pentest Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin:0; padding:0; background:#0f1117; color:#e2e8f0; }}
  .container {{ max-width:960px; margin:0 auto; padding:40px 24px; }}
  h1 {{ font-size:28px; font-weight:700; margin-bottom:4px; color:#fff; }}
  .meta {{ font-size:13px; color:#64748b; margin-bottom:32px; }}
  .finding {{ border:1px solid #1e293b; border-radius:12px; padding:24px; margin-bottom:20px; background:#141720; }}
  .finding-header {{ display:flex; align-items:center; gap:12px; margin-bottom:12px; }}
  .finding-title {{ font-size:16px; font-weight:600; color:#f1f5f9; }}
  .badge {{ padding:3px 10px; border-radius:999px; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.5px; }}
  .critical {{ background:#7f1d1d; color:#fca5a5; }}
  .high {{ background:#431407; color:#fdba74; }}
  .medium {{ background:#422006; color:#fcd34d; }}
  .low {{ background:#052e16; color:#86efac; }}
  .info {{ background:#0c1a2e; color:#93c5fd; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:12px; }}
  th {{ text-align:left; padding:8px 12px; background:#1e293b; color:#94a3b8; font-weight:500; }}
  td {{ padding:8px 12px; border-top:1px solid #1e293b; color:#cbd5e1; vertical-align:top; }}
  .summary-grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:32px; }}
  .summary-card {{ background:#141720; border:1px solid #1e293b; border-radius:12px; padding:16px; text-align:center; }}
  .summary-count {{ font-size:32px; font-weight:700; }}
  .summary-label {{ font-size:12px; color:#64748b; margin-top:4px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Penetration Test Report</h1>
  <p class="meta">Generated: {generated_at} &nbsp;|&nbsp; Findings: {total}</p>

  <div class="summary-grid">
    {severity_cards}
  </div>

  {finding_sections}
</div>
</body>
</html>"""

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
_SEVERITY_COLORS = {
    "critical": "#ef4444", "high": "#f97316",
    "medium": "#eab308", "low": "#22c55e", "info": "#3b82f6",
}


def findings_to_html(findings: list[dict[str, Any]], title: str = "Pentest Report") -> bytes:
    counts: dict[str, int] = {s: 0 for s in _SEVERITY_ORDER}
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        counts[sev] = counts.get(sev, 0) + 1

    cards = "".join(
        f'<div class="summary-card">'
        f'<div class="summary-count" style="color:{_SEVERITY_COLORS.get(s, "#fff")}">{counts[s]}</div>'
        f'<div class="summary-label">{s.title()}</div></div>'
        for s in _SEVERITY_ORDER
    )

    sections = []
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        cves = ", ".join(f.get("cve") or []) or "—"
        mitre = ", ".join(f.get("mitre_techniques") or []) or "—"
        sections.append(
            f'<div class="finding">'
            f'<div class="finding-header">'
            f'<span class="badge {sev}">{sev}</span>'
            f'<span class="finding-title">{f.get("title", "Untitled")}</span>'
            f'</div>'
            f'<table><tr><th>Field</th><th>Value</th></tr>'
            f'<tr><td>CVE</td><td>{cves}</td></tr>'
            f'<tr><td>MITRE</td><td>{mitre}</td></tr>'
            f'<tr><td>Description</td><td>{f.get("description", "")}</td></tr>'
            f'<tr><td>Status</td><td>{f.get("status", "open")}</td></tr>'
            f'</table></div>'
        )

    html = _HTML_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total=len(findings),
        severity_cards=cards,
        finding_sections="\n".join(sections),
    )
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

_CSV_COLUMNS = [
    "id", "title", "severity", "status", "cve", "mitre_techniques",
    "description", "remediation", "created_at",
]


def findings_to_csv(findings: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for f in findings:
        row = {k: f.get(k, "") for k in _CSV_COLUMNS}
        # Normalise list fields
        for key in ("cve", "mitre_techniques"):
            val = row[key]
            if isinstance(val, list):
                row[key] = "; ".join(val)
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# STIX 2.1
# ---------------------------------------------------------------------------

_STIX_SEVERITY_TO_SCORE = {
    "critical": "10.0", "high": "8.0",
    "medium": "5.0", "low": "2.0", "info": "0.0",
}


def findings_to_stix(
    findings: list[dict[str, Any]],
    engagement_name: str = "Pentest Engagement",
    identity_name: str = "OSINT Platform",
) -> bytes:
    """Build a minimal STIX 2.1 Bundle with Vulnerability and Note SDOs."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    identity_id = f"identity--{uuid.uuid4()}"

    objects: list[dict[str, Any]] = [
        {
            "type": "identity",
            "spec_version": "2.1",
            "id": identity_id,
            "created": now,
            "modified": now,
            "name": identity_name,
            "identity_class": "system",
        }
    ]

    for f in findings:
        finding_id = str(f.get("id", uuid.uuid4()))
        sev = str(f.get("severity", "info")).lower()
        vuln_id = f"vulnerability--{uuid.uuid4()}"
        note_id = f"note--{uuid.uuid4()}"
        cves: list[str] = f.get("cve") or []

        vuln: dict[str, Any] = {
            "type": "vulnerability",
            "spec_version": "2.1",
            "id": vuln_id,
            "created": now,
            "modified": now,
            "name": f.get("title", f"Finding {finding_id}"),
            "description": f.get("description", ""),
            "created_by_ref": identity_id,
        }
        if cves:
            vuln["external_references"] = [
                {"source_name": "cve", "external_id": c} for c in cves
            ]

        cvss_score = _STIX_SEVERITY_TO_SCORE.get(sev, "0.0")
        vuln["labels"] = [sev, f"cvss:{cvss_score}"]

        mitre = f.get("mitre_techniques") or []
        if mitre:
            vuln["external_references"] = vuln.get("external_references", []) + [
                {"source_name": "mitre-attack", "external_id": t} for t in mitre
            ]

        note: dict[str, Any] = {
            "type": "note",
            "spec_version": "2.1",
            "id": note_id,
            "created": now,
            "modified": now,
            "created_by_ref": identity_id,
            "abstract": f"Status: {f.get('status', 'open')}",
            "content": f.get("remediation", "No remediation notes."),
            "object_refs": [vuln_id],
        }

        objects.extend([vuln, note])

    bundle: dict[str, Any] = {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "objects": objects,
    }
    return json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8")
