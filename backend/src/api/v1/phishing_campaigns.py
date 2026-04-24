"""Phishing Campaign Manager — authorized pentest simulation endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import random
from datetime import datetime

router = APIRouter(prefix="/api/v1/phishing-campaigns", tags=["phishing-campaigns"])

# In-memory store
_campaigns: dict[str, dict] = {}


class PhishingTemplate(BaseModel):
    id: str
    name: str
    category: str  # credential_harvest, malware_delivery, pretexting
    subject: str
    preview: str
    success_rate_avg: float


class PhishingCampaign(BaseModel):
    id: str
    name: str
    status: str  # draft, running, paused, completed
    template_id: str
    target_count: int
    sent_count: int
    opened_count: int
    clicked_count: int
    submitted_count: int
    start_date: Optional[str]
    end_date: Optional[str]
    authorized_by: str
    engagement_id: str
    created_at: str


class CreateCampaignInput(BaseModel):
    name: str
    template_id: str
    target_count: int
    authorized_by: str
    engagement_id: str


TEMPLATES = [
    PhishingTemplate(
        id="t1",
        name="IT Security Alert",
        category="credential_harvest",
        subject="[URGENT] Your password expires in 24 hours",
        preview="Please update your corporate password immediately...",
        success_rate_avg=0.23,
    ),
    PhishingTemplate(
        id="t2",
        name="CEO Wire Transfer",
        category="pretexting",
        subject="Confidential - Urgent wire transfer needed",
        preview="I need you to process an urgent payment...",
        success_rate_avg=0.08,
    ),
    PhishingTemplate(
        id="t3",
        name="HR Benefits Update",
        category="credential_harvest",
        subject="Action Required: Update your benefits portal",
        preview="Your annual benefits enrollment closes Friday...",
        success_rate_avg=0.31,
    ),
    PhishingTemplate(
        id="t4",
        name="Document Review",
        category="malware_delivery",
        subject="Please review the attached contract",
        preview="Hi, please find the contract attached for your review...",
        success_rate_avg=0.18,
    ),
]


@router.get("/templates", response_model=list[PhishingTemplate])
async def list_templates() -> list[PhishingTemplate]:
    return TEMPLATES


@router.get("/campaigns", response_model=list[PhishingCampaign])
async def list_campaigns() -> list[PhishingCampaign]:
    return [PhishingCampaign(**c) for c in _campaigns.values()]


@router.post("/campaigns", response_model=PhishingCampaign)
async def create_campaign(data: CreateCampaignInput) -> PhishingCampaign:
    cid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    campaign: dict = {
        "id": cid,
        "name": data.name,
        "status": "draft",
        "template_id": data.template_id,
        "target_count": data.target_count,
        "sent_count": 0,
        "opened_count": 0,
        "clicked_count": 0,
        "submitted_count": 0,
        "start_date": None,
        "end_date": None,
        "authorized_by": data.authorized_by,
        "engagement_id": data.engagement_id,
        "created_at": now,
    }
    _campaigns[cid] = campaign
    return PhishingCampaign(**campaign)


@router.post("/campaigns/{campaign_id}/launch", response_model=PhishingCampaign)
async def launch_campaign(campaign_id: str) -> PhishingCampaign:
    if campaign_id not in _campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")
    c = _campaigns[campaign_id]
    c["status"] = "running"
    c["start_date"] = datetime.utcnow().isoformat()
    c["sent_count"] = c["target_count"]
    c["opened_count"] = int(c["target_count"] * random.uniform(0.3, 0.7))
    c["clicked_count"] = int(c["opened_count"] * random.uniform(0.2, 0.5))
    c["submitted_count"] = int(c["clicked_count"] * random.uniform(0.3, 0.7))
    return PhishingCampaign(**c)


@router.get("/campaigns/{campaign_id}/report")
async def campaign_report(campaign_id: str) -> dict:
    if campaign_id not in _campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")
    c = _campaigns[campaign_id]
    click_rate = c["clicked_count"] / c["sent_count"] if c["sent_count"] > 0 else 0
    return {
        "campaign_id": campaign_id,
        "open_rate": c["opened_count"] / c["sent_count"] if c["sent_count"] > 0 else 0,
        "click_rate": click_rate,
        "submission_rate": c["submitted_count"] / c["sent_count"] if c["sent_count"] > 0 else 0,
        "risk_score": min(100, int(click_rate * 200)),
        "department_breakdown": [
            {"department": "Finance", "clicked": random.randint(0, 5)},
            {"department": "HR", "clicked": random.randint(0, 3)},
            {"department": "Engineering", "clicked": random.randint(0, 2)},
        ],
        "time_to_click_avg_minutes": random.randint(2, 45),
    }
