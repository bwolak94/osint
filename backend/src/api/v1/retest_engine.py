from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, random
from datetime import datetime

router = APIRouter(prefix="/api/v1/retest-engine", tags=["retest-engine"])

_retests: dict[str, dict] = {}


class RetestItem(BaseModel):
    id: str
    finding_id: str
    finding_title: str
    severity: str
    original_cvss: float
    status: str  # pending, in_progress, passed, failed, skipped
    result: Optional[str]  # remediated, still_vulnerable, partially_remediated
    tested_at: Optional[str]
    notes: str
    automated: bool


class RetestSession(BaseModel):
    id: str
    name: str
    engagement_id: str
    items: list[RetestItem]
    total_items: int
    passed: int
    failed: int
    pending: int
    completion_percentage: float
    created_at: str
    status: str


class CreateRetestInput(BaseModel):
    name: str
    engagement_id: str
    finding_ids: list[str]


SAMPLE_FINDINGS = [
    ("f1", "SQL Injection in login form", "critical", 9.8),
    ("f2", "Stored XSS in comment field", "high", 8.2),
    ("f3", "IDOR in user profile endpoint", "high", 7.5),
    ("f4", "Outdated Apache version", "medium", 5.3),
    ("f5", "Missing security headers", "low", 3.1),
]


@router.get("/sessions", response_model=list[RetestSession])
async def list_sessions():
    return [RetestSession(**s) for s in _retests.values()]


@router.post("/sessions", response_model=RetestSession)
async def create_session(data: CreateRetestInput):
    sid = str(uuid.uuid4())
    items = []
    for fid, title, sev, cvss in SAMPLE_FINDINGS:
        items.append(
            RetestItem(
                id=str(uuid.uuid4()),
                finding_id=fid,
                finding_title=title,
                severity=sev,
                original_cvss=cvss,
                status="pending",
                result=None,
                tested_at=None,
                notes="",
                automated=random.random() > 0.4,
            ).model_dump()
        )

    session = {
        "id": sid,
        "name": data.name,
        "engagement_id": data.engagement_id,
        "items": items,
        "total_items": len(items),
        "passed": 0,
        "failed": 0,
        "pending": len(items),
        "completion_percentage": 0.0,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending",
    }
    _retests[sid] = session
    return RetestSession(**session)


@router.post("/sessions/{session_id}/run-automated", response_model=RetestSession)
async def run_automated(session_id: str):
    if session_id not in _retests:
        raise HTTPException(status_code=404, detail="Session not found")
    session = _retests[session_id]
    session["status"] = "running"

    for item in session["items"]:
        if item["automated"] and item["status"] == "pending":
            item["status"] = random.choice(["passed", "failed"])
            item["result"] = (
                "remediated"
                if item["status"] == "passed"
                else random.choice(["still_vulnerable", "partially_remediated"])
            )
            item["tested_at"] = datetime.utcnow().isoformat()

    passed = sum(1 for i in session["items"] if i["status"] == "passed")
    failed = sum(1 for i in session["items"] if i["status"] == "failed")
    pending = sum(1 for i in session["items"] if i["status"] == "pending")

    session.update(
        {
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "completion_percentage": round(
                (passed + failed) / len(session["items"]) * 100, 1
            ),
            "status": "completed" if pending == 0 else "partial",
        }
    )
    return RetestSession(**session)


@router.patch("/sessions/{session_id}/items/{item_id}", response_model=RetestSession)
async def update_item(session_id: str, item_id: str, status: str, notes: str = ""):
    if session_id not in _retests:
        raise HTTPException(status_code=404, detail="Session not found")
    session = _retests[session_id]
    for item in session["items"]:
        if item["id"] == item_id:
            item["status"] = status
            item["result"] = "remediated" if status == "passed" else "still_vulnerable"
            item["tested_at"] = datetime.utcnow().isoformat()
            if notes:
                item["notes"] = notes

    passed = sum(1 for i in session["items"] if i["status"] == "passed")
    failed = sum(1 for i in session["items"] if i["status"] == "failed")
    pending = sum(1 for i in session["items"] if i["status"] == "pending")
    session.update(
        {
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "completion_percentage": round(
                (passed + failed) / len(session["items"]) * 100, 1
            ),
        }
    )
    return RetestSession(**session)
