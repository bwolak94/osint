from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random

router = APIRouter(prefix="/api/v1/phone-intel", tags=["phone-intel"])

class PhoneCarrierInfo(BaseModel):
    name: str
    type: str  # mobile, landline, voip
    country: str
    country_code: str

class PhoneIntelResult(BaseModel):
    phone_number: str
    formatted: str
    country: str
    country_code: str
    carrier: PhoneCarrierInfo
    line_type: str
    is_valid: bool
    is_disposable: bool
    is_voip: bool
    timezone: str
    location: Optional[str]
    spam_score: int
    spam_reports: int
    breach_count: int
    social_profiles_found: list[str]
    associated_emails: list[str]
    associated_names: list[str]
    risk_level: str

@router.get("/lookup", response_model=PhoneIntelResult)
async def phone_lookup(phone: str):
    """Lookup intelligence on a phone number"""
    spam_score = random.randint(0, 100)
    breach_count = random.randint(0, 5)
    is_voip = random.random() < 0.3

    return PhoneIntelResult(
        phone_number=phone,
        formatted=phone,
        country=random.choice(["United States", "United Kingdom", "Germany", "France", "Canada"]),
        country_code=random.choice(["US", "GB", "DE", "FR", "CA"]),
        carrier=PhoneCarrierInfo(
            name=random.choice(["Verizon", "AT&T", "T-Mobile", "Google Voice", "Twilio", "Vonage"]),
            type="voip" if is_voip else random.choice(["mobile", "landline"]),
            country="United States",
            country_code="US"
        ),
        line_type="voip" if is_voip else random.choice(["mobile", "landline"]),
        is_valid=True,
        is_disposable=random.random() < 0.15,
        is_voip=is_voip,
        timezone=random.choice(["America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Berlin"]),
        location=random.choice(["New York, NY", "Los Angeles, CA", "London, UK", None]),
        spam_score=spam_score,
        spam_reports=random.randint(0, 50) if spam_score > 50 else 0,
        breach_count=breach_count,
        social_profiles_found=random.sample(["WhatsApp", "Telegram", "Signal", "Facebook", "LinkedIn"], random.randint(0, 3)),
        associated_emails=[f"user{random.randint(1,99)}@example.com"] if breach_count > 0 else [],
        associated_names=["John Smith"] if breach_count > 0 else [],
        risk_level="high" if spam_score > 70 or is_voip else "medium" if spam_score > 40 else "low"
    )
