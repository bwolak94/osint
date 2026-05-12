from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/vuln-management", tags=["vuln-management"])

_vulns: dict[str, dict] = {}

def _seed() -> None:
    if _vulns:
        return
    templates = [
        ("CVE-2024-1234", "Apache Log4Shell variant", "critical", "network", 9.8),
        ("CVE-2024-5678", "SQL Injection in customer portal", "high", "web", 8.2),
        ("CVE-2023-9012", "Outdated OpenSSL", "medium", "network", 5.9),
        ("CVE-2024-3456", "Exposed debug endpoint", "high", "web", 7.5),
        ("CUSTOM-001", "Default admin credentials", "critical", "configuration", 9.1),
    ]
    for cve, title, sev, category, cvss in templates:
        vid = str(uuid.uuid4())
        _vulns[vid] = {
            "id": vid,
            "cve_id": cve,
            "title": title,
            "severity": sev,
            "cvss_score": cvss,
            "category": category,
            "status": random.choice(["open", "in_progress", "remediated", "accepted_risk"]),
            "affected_assets": [f"host{random.randint(1,5)}.internal", f"10.0.0.{random.randint(1,254)}"],
            "description": f"Security vulnerability: {title}",
            "remediation": "Apply vendor patch or implement workaround",
            "discovered_at": (datetime.utcnow() - timedelta(days=random.randint(1, 90))).isoformat(),
            "due_date": (datetime.utcnow() + timedelta(days=random.randint(1, 30))).isoformat(),
            "assignee": random.choice(["alice@team.com", "bob@team.com", None]),
            "tags": [category, sev],
        }

_seed()

class Vulnerability(BaseModel):
    id: str
    cve_id: Optional[str]
    title: str
    severity: str
    cvss_score: float
    category: str
    status: str
    affected_assets: list[str]
    description: str
    remediation: str
    discovered_at: str
    due_date: Optional[str]
    assignee: Optional[str]
    tags: list[str]

class UpdateVulnInput(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None

@router.get("", response_model=list[Vulnerability])
async def list_vulns(severity: Optional[str] = None, status: Optional[str] = None):
    items = [Vulnerability(**v) for v in _vulns.values()]
    if severity:
        items = [i for i in items if i.severity == severity]
    if status:
        items = [i for i in items if i.status == status]
    return sorted(items, key=lambda v: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(v.severity, 4))

@router.patch("/{vuln_id}", response_model=Vulnerability)
async def update_vuln(vuln_id: str, data: UpdateVulnInput):
    if vuln_id not in _vulns:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    if data.status:
        _vulns[vuln_id]["status"] = data.status
    if data.assignee is not None:
        _vulns[vuln_id]["assignee"] = data.assignee
    return Vulnerability(**_vulns[vuln_id])
