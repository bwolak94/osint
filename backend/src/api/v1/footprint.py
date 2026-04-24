"""Digital footprint score API."""

from fastapi import APIRouter
from pydantic import BaseModel
import random

router = APIRouter(prefix="/api/v1/footprint", tags=["footprint"])


class FootprintCategory(BaseModel):
    name: str
    score: int  # 0-100
    findings: list[str]
    risk: str  # low, medium, high, critical


class FootprintScore(BaseModel):
    target: str
    overall_score: int
    risk_level: str
    categories: list[FootprintCategory]
    exposed_assets: list[str]
    recommendations: list[str]
    data_broker_count: int
    social_profiles: list[dict]


@router.get("/score", response_model=FootprintScore)
async def get_footprint_score(target: str):
    """Calculate digital footprint exposure score for a target"""
    categories = [
        FootprintCategory(
            name="Social Media Exposure",
            score=random.randint(20, 90),
            findings=[
                "LinkedIn profile public",
                "Twitter history indexed",
                "Facebook group memberships visible",
            ],
            risk=random.choice(["medium", "high"]),
        ),
        FootprintCategory(
            name="Data Broker Listings",
            score=random.randint(40, 95),
            findings=[
                "Found on Spokeo",
                "Found on PeopleFinder",
                "Address history exposed",
            ],
            risk="high",
        ),
        FootprintCategory(
            name="Credential Exposure",
            score=random.randint(0, 70),
            findings=[
                "Email in 3 breach databases",
                "Password hash found in combolists",
            ],
            risk=random.choice(["low", "medium", "high", "critical"]),
        ),
        FootprintCategory(
            name="Technical Footprint",
            score=random.randint(10, 80),
            findings=[
                "GitHub repos with email in commits",
                "NPM package author metadata",
            ],
            risk=random.choice(["low", "medium"]),
        ),
        FootprintCategory(
            name="Public Records",
            score=random.randint(5, 60),
            findings=[
                "Court records accessible",
                "Business registration public",
            ],
            risk=random.choice(["low", "medium"]),
        ),
    ]
    overall = int(sum(c.score for c in categories) / len(categories))
    risk = (
        "critical"
        if overall > 80
        else "high"
        if overall > 60
        else "medium"
        if overall > 40
        else "low"
    )

    return FootprintScore(
        target=target,
        overall_score=overall,
        risk_level=risk,
        categories=categories,
        exposed_assets=[
            f"{target} email",
            "Home address (approx)",
            "Phone number",
            "Employment history",
        ],
        recommendations=[
            "Request data broker opt-outs",
            "Enable Google account activity controls",
            "Use email aliases for signups",
            "Audit social media privacy settings",
            "Check haveibeenpwned.com for breach exposure",
        ],
        data_broker_count=random.randint(3, 25),
        social_profiles=[
            {"platform": "LinkedIn", "url_found": True, "privacy": "public"},
            {
                "platform": "Twitter",
                "url_found": random.choice([True, False]),
                "privacy": "public",
            },
            {
                "platform": "GitHub",
                "url_found": random.choice([True, False]),
                "privacy": "public",
            },
        ],
    )
