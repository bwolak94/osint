from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/corporate-intel", tags=["corporate-intel"])

class Executive(BaseModel):
    name: str
    title: str
    linkedin_found: bool
    email_pattern: Optional[str]
    previous_companies: list[str]

class Subsidiary(BaseModel):
    name: str
    country: str
    registration_number: Optional[str]
    active: bool

class CorporateProfile(BaseModel):
    company_name: str
    registration_number: Optional[str]
    country: str
    industry: str
    founded_year: Optional[int]
    employee_count_range: str
    revenue_range: Optional[str]
    website: str
    technologies: list[str]
    executives: list[Executive]
    subsidiaries: list[Subsidiary]
    domains: list[str]
    ip_ranges: list[str]
    open_jobs: int
    news_count: int
    risk_indicators: list[str]

@router.get("/profile", response_model=CorporateProfile)
async def get_corporate_profile(company: str, country: str = "US"):
    executives = [
        Executive(name="John Smith", title="CEO", linkedin_found=True, email_pattern=f"j.smith@{company.lower().replace(' ', '')}.com", previous_companies=["Previous Corp", "Tech Startup Inc"]),
        Executive(name="Jane Doe", title="CTO", linkedin_found=True, email_pattern=f"j.doe@{company.lower().replace(' ', '')}.com", previous_companies=["Big Tech Ltd"]),
        Executive(name="Bob Johnson", title="CFO", linkedin_found=random.choice([True, False]), email_pattern=None, previous_companies=["Finance Corp"]),
    ]

    subsidiaries = [
        Subsidiary(name=f"{company} {c}", country=c, registration_number=f"REG{random.randint(10000,99999)}", active=True)
        for c in random.sample(["UK", "DE", "FR", "CA", "AU", "SG"], random.randint(1, 4))
    ]

    tech = random.sample(["AWS", "Cloudflare", "React", "Java", "Python", "Kubernetes", "Salesforce", "HubSpot", "Slack", "GitHub"], random.randint(3, 7))
    domain = f"{company.lower().replace(' ', '')}.com"

    return CorporateProfile(
        company_name=company,
        registration_number=f"US{random.randint(1000000, 9999999)}",
        country=country,
        industry=random.choice(["Technology", "Finance", "Healthcare", "Manufacturing", "Retail", "Consulting"]),
        founded_year=random.randint(1990, 2020),
        employee_count_range=random.choice(["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]),
        revenue_range=random.choice(["<1M", "1-10M", "10-50M", "50-100M", "100M+"]),
        website=f"https://{domain}",
        technologies=tech,
        executives=executives,
        subsidiaries=subsidiaries,
        domains=[domain, f"www.{domain}", f"mail.{domain}"],
        ip_ranges=[f"{random.randint(1,254)}.{random.randint(1,254)}.0.0/24"],
        open_jobs=random.randint(0, 50),
        news_count=random.randint(0, 20),
        risk_indicators=random.sample([
            "Recent litigation disclosed in filings",
            "Key executive departure last quarter",
            "Regulatory investigation reported"
        ], random.randint(0, 2))
    )
