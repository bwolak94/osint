from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/sla", tags=["sla"])

class SlaItem(BaseModel):
    id: str
    title: str
    type: str  # finding, deliverable, meeting, remediation
    severity: str
    engagement_id: str
    due_date: str
    status: str  # on_track, at_risk, breached, completed
    days_remaining: int
    assignee: Optional[str]
    escalated: bool
    escalation_level: int  # 0=none, 1=manager, 2=director, 3=executive

class SlaMetrics(BaseModel):
    total_items: int
    on_track: int
    at_risk: int
    breached: int
    completed: int
    breach_rate: float
    avg_days_remaining: float
    items: list[SlaItem]

@router.get("/metrics", response_model=SlaMetrics)
async def get_sla_metrics(engagement_id: Optional[str] = None):
    items = []
    types = ["finding", "deliverable", "meeting", "remediation"]

    for i in range(12):
        days = random.randint(-5, 30)
        status = "breached" if days < 0 else "completed" if random.random() < 0.2 else "at_risk" if days < 5 else "on_track"
        esc = status == "breached" or (status == "at_risk" and random.random() < 0.3)
        items.append(SlaItem(
            id=f"sla_{i}", title=f"SLA Item {i + 1}: {random.choice(['Critical finding remediation', 'Pentest report delivery', 'Kickoff meeting', 'Vulnerability retest'])}",
            type=random.choice(types), severity=random.choice(["critical", "high", "medium", "low"]),
            engagement_id=engagement_id or f"ENG-2024-{random.randint(1,3):03d}",
            due_date=(datetime.utcnow() + timedelta(days=days)).isoformat(),
            status=status, days_remaining=days, assignee=random.choice(["alice@team.com", "bob@team.com", None]),
            escalated=esc, escalation_level=2 if esc and days < -3 else 1 if esc else 0
        ))

    counts = {s: sum(1 for x in items if x.status == s) for s in ["on_track", "at_risk", "breached", "completed"]}
    breached_count = counts["breached"]
    total_active = len(items) - counts["completed"]

    return SlaMetrics(
        total_items=len(items), on_track=counts["on_track"], at_risk=counts["at_risk"],
        breached=breached_count, completed=counts["completed"],
        breach_rate=round(breached_count / total_active * 100, 1) if total_active > 0 else 0,
        avg_days_remaining=round(sum(x.days_remaining for x in items if x.status != "completed") / max(1, total_active), 1),
        items=items
    )
