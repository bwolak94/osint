from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/methodology", tags=["methodology"])

_assessments: dict[str, dict] = {}

class MethodologyStep(BaseModel):
    id: str
    phase: str
    name: str
    description: str
    required: bool
    checklist_items: list[str]
    references: list[str]  # OWASP, PTES, etc.

class Assessment(BaseModel):
    id: str
    name: str
    methodology: str  # PTES, OWASP, NIST, custom
    status: str
    completed_steps: list[str]
    total_steps: int
    completion_percentage: float
    created_at: str
    engagement_id: str

PTES_STEPS = [
    MethodologyStep(id="ptes-1", phase="Pre-Engagement", name="Scope Definition", description="Define the scope, rules of engagement, and authorization", required=True, checklist_items=["Written authorization obtained", "Scope document signed", "Emergency contacts established", "Out-of-scope systems identified"], references=["PTES Technical Guidelines v2"]),
    MethodologyStep(id="ptes-2", phase="Intelligence Gathering", name="OSINT Collection", description="Gather open source intelligence about the target", required=True, checklist_items=["DNS enumeration complete", "WHOIS data collected", "Social media profiled", "Job postings analyzed", "Technology fingerprinting done"], references=["PTES Intelligence Gathering"]),
    MethodologyStep(id="ptes-3", phase="Threat Modeling", name="Attack Surface Analysis", description="Model threats and prioritize attack vectors", required=True, checklist_items=["Attack surface mapped", "Asset criticality rated", "Threat actors profiled", "Attack vectors prioritized"], references=["STRIDE Methodology"]),
    MethodologyStep(id="ptes-4", phase="Vulnerability Analysis", name="Vulnerability Scanning", description="Identify and validate vulnerabilities", required=True, checklist_items=["Automated scan complete", "Manual verification done", "False positives removed", "CVSSv3 scores assigned"], references=["OWASP Testing Guide v4"]),
    MethodologyStep(id="ptes-5", phase="Exploitation", name="Exploitation", description="Attempt to exploit discovered vulnerabilities", required=False, checklist_items=["Exploitation authorized in scope", "Staging tested first", "Impact documented", "Cleanup performed"], references=["PTES Exploitation"]),
    MethodologyStep(id="ptes-6", phase="Post-Exploitation", name="Lateral Movement & Persistence", description="Demonstrate impact through post-exploitation", required=False, checklist_items=["Lateral movement documented", "Data exfiltration simulated", "Persistence demonstrated", "Evidence preserved"], references=["MITRE ATT&CK"]),
    MethodologyStep(id="ptes-7", phase="Reporting", name="Report Generation", description="Document all findings and remediation guidance", required=True, checklist_items=["Executive summary written", "Technical findings documented", "CVSS scores assigned", "Remediation steps provided", "Report peer-reviewed"], references=["PTES Reporting"]),
]

@router.get("/steps", response_model=list[MethodologyStep])
async def list_steps(methodology: str = "PTES"):
    return PTES_STEPS

@router.get("/assessments", response_model=list[Assessment])
async def list_assessments():
    return [Assessment(**a) for a in _assessments.values()]

@router.post("/assessments", response_model=Assessment)
async def create_assessment(name: str, methodology: str = "PTES", engagement_id: str = ""):
    aid = str(uuid.uuid4())
    assessment = {
        "id": aid, "name": name, "methodology": methodology, "status": "in_progress",
        "completed_steps": [], "total_steps": len(PTES_STEPS),
        "completion_percentage": 0.0, "created_at": datetime.utcnow().isoformat(), "engagement_id": engagement_id
    }
    _assessments[aid] = assessment
    return Assessment(**assessment)

@router.post("/assessments/{assessment_id}/complete-step", response_model=Assessment)
async def complete_step(assessment_id: str, step_id: str):
    if assessment_id not in _assessments:
        raise HTTPException(status_code=404, detail="Assessment not found")
    a = _assessments[assessment_id]
    if step_id not in a["completed_steps"]:
        a["completed_steps"].append(step_id)
    a["completion_percentage"] = round(len(a["completed_steps"]) / a["total_steps"] * 100, 1)
    if a["completion_percentage"] >= 100:
        a["status"] = "completed"
    return Assessment(**a)
