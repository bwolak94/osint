from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime, timedelta
import random

router = APIRouter(prefix="/api/v1/time-tracking", tags=["time-tracking"])

_entries: dict[str, dict] = {}
_active_timer: Optional[dict] = None

class TimeEntry(BaseModel):
    id: str
    engagement_id: str
    category: str  # reconnaissance, exploitation, reporting, meeting, admin
    description: str
    start_time: str
    end_time: Optional[str]
    duration_minutes: Optional[int]
    billable: bool
    hourly_rate: float
    amount: float
    created_at: str

class StartTimerInput(BaseModel):
    engagement_id: str
    category: str
    description: str
    billable: bool = True
    hourly_rate: float = 150.0

class ManualEntryInput(BaseModel):
    engagement_id: str
    category: str
    description: str
    duration_minutes: int
    billable: bool = True
    hourly_rate: float = 150.0

# Seed demo data
def _seed():
    if _entries: return
    categories = ["reconnaissance", "exploitation", "reporting", "meeting", "admin"]
    for i in range(8):
        eid = str(uuid.uuid4())
        dur = random.randint(30, 240)
        rate = 150.0
        start = (datetime.utcnow() - timedelta(days=random.randint(1, 14), hours=random.randint(0, 8))).isoformat()
        end = (datetime.fromisoformat(start) + timedelta(minutes=dur)).isoformat()
        _entries[eid] = {
            "id": eid, "engagement_id": f"ENG-2024-{i // 4 + 1:03d}",
            "category": random.choice(categories),
            "description": f"Sample work item {i + 1}",
            "start_time": start, "end_time": end, "duration_minutes": dur,
            "billable": random.random() > 0.2, "hourly_rate": rate,
            "amount": round(dur / 60 * rate, 2), "created_at": start
        }

_seed()

@router.get("/entries", response_model=list[TimeEntry])
async def list_entries(engagement_id: Optional[str] = None):
    entries = list(_entries.values())
    if engagement_id:
        entries = [e for e in entries if e["engagement_id"] == engagement_id]
    return sorted([TimeEntry(**e) for e in entries], key=lambda x: x.start_time, reverse=True)

@router.post("/start", response_model=TimeEntry)
async def start_timer(data: StartTimerInput):
    global _active_timer
    eid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    entry = {
        "id": eid, "engagement_id": data.engagement_id, "category": data.category,
        "description": data.description, "start_time": now, "end_time": None,
        "duration_minutes": None, "billable": data.billable, "hourly_rate": data.hourly_rate,
        "amount": 0.0, "created_at": now
    }
    _entries[eid] = entry
    _active_timer = {"entry_id": eid, "start_time": now}
    return TimeEntry(**entry)

@router.post("/stop", response_model=TimeEntry)
async def stop_timer():
    global _active_timer
    if not _active_timer:
        raise HTTPException(status_code=400, detail="No active timer")
    eid = _active_timer["entry_id"]
    entry = _entries[eid]
    now = datetime.utcnow()
    start = datetime.fromisoformat(entry["start_time"])
    dur = max(1, int((now - start).total_seconds() / 60))
    entry["end_time"] = now.isoformat()
    entry["duration_minutes"] = dur
    entry["amount"] = round(dur / 60 * entry["hourly_rate"], 2)
    _active_timer = None
    return TimeEntry(**entry)

@router.post("/manual", response_model=TimeEntry)
async def add_manual(data: ManualEntryInput):
    eid = str(uuid.uuid4())
    now = datetime.utcnow()
    start = (now - timedelta(minutes=data.duration_minutes)).isoformat()
    entry = {
        "id": eid, "engagement_id": data.engagement_id, "category": data.category,
        "description": data.description, "start_time": start, "end_time": now.isoformat(),
        "duration_minutes": data.duration_minutes, "billable": data.billable,
        "hourly_rate": data.hourly_rate, "amount": round(data.duration_minutes / 60 * data.hourly_rate, 2),
        "created_at": now.isoformat()
    }
    _entries[eid] = entry
    return TimeEntry(**entry)

@router.get("/summary")
async def get_summary(engagement_id: Optional[str] = None):
    entries = list(_entries.values())
    if engagement_id:
        entries = [e for e in entries if e["engagement_id"] == engagement_id]
    billable = [e for e in entries if e["billable"] and e["duration_minutes"]]
    total_hours = sum(e["duration_minutes"] for e in billable if e["duration_minutes"]) / 60
    total_amount = sum(e["amount"] for e in billable)
    by_category: dict = {}
    for e in entries:
        cat = e["category"]
        by_category[cat] = by_category.get(cat, {"minutes": 0, "amount": 0})
        by_category[cat]["minutes"] += e.get("duration_minutes") or 0
        by_category[cat]["amount"] += e.get("amount") or 0
    return {"total_hours": round(total_hours, 2), "total_amount": round(total_amount, 2), "billable_entries": len(billable), "by_category": by_category}
