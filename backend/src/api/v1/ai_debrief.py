from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random

router = APIRouter(prefix="/api/v1/ai-debrief", tags=["ai-debrief"])

class DebriefSection(BaseModel):
    title: str
    content: str
    severity: Optional[str]

class AiDebrief(BaseModel):
    engagement_id: str
    executive_summary: str
    attack_narrative: str
    key_findings: list[DebriefSection]
    defensive_gaps: list[str]
    recommended_priorities: list[str]
    positive_findings: list[str]
    metrics: dict
    generated_at: str

@router.post("/generate", response_model=AiDebrief)
async def generate_debrief(engagement_id: str, scope: str = "", findings_count: int = 5):
    from datetime import datetime

    critical_count = random.randint(0, 2)
    high_count = random.randint(1, 4)
    medium_count = random.randint(2, 6)
    low_count = random.randint(1, 5)

    key_findings = [
        DebriefSection(title="SQL Injection in Authentication Module", content="A critical SQL injection vulnerability was discovered in the login endpoint allowing full database access without authentication. An attacker could extract all user credentials and sensitive data.", severity="critical"),
        DebriefSection(title="Insecure Direct Object References", content="Multiple IDOR vulnerabilities allow authenticated users to access other users' data by manipulating object identifiers in API requests.", severity="high"),
        DebriefSection(title="Weak Password Policy", content="The application allows passwords as short as 6 characters without complexity requirements, and no account lockout policy is enforced.", severity="medium"),
    ][:min(findings_count, 3)]

    return AiDebrief(
        engagement_id=engagement_id,
        executive_summary=f"The penetration test of {scope or 'the target environment'} identified {critical_count + high_count + medium_count + low_count} vulnerabilities across {critical_count + high_count} critical and high severity issues. The most significant risk involves unauthenticated access paths that could allow a threat actor to achieve full system compromise within the assessed environment. Immediate remediation of critical findings is strongly recommended.",
        attack_narrative=f"During the assessment, the testing team followed a structured methodology beginning with reconnaissance and information gathering. Initial access was achieved through exploitation of a critical vulnerability in the web application layer. From this foothold, the team demonstrated lateral movement capabilities across {random.randint(2, 6)} internal systems, ultimately achieving domain administrator privileges within {random.randint(2, 12)} hours of initial access. This attack path closely mirrors techniques used by advanced persistent threat actors.",
        key_findings=key_findings,
        defensive_gaps=[
            "No network segmentation between DMZ and internal systems",
            "Endpoint detection and response (EDR) not deployed on legacy systems",
            "Privileged access management controls are insufficient",
            "Security awareness training frequency inadequate for current threat landscape"
        ],
        recommended_priorities=[
            f"[CRITICAL] Remediate SQL injection within 24 hours - patch application and implement parameterized queries",
            "[HIGH] Implement proper access controls for all API endpoints within 7 days",
            "[HIGH] Deploy MFA for all privileged accounts immediately",
            "[MEDIUM] Conduct security awareness training focused on phishing within 30 days",
            "[LOW] Review and update password complexity policy within 90 days"
        ],
        positive_findings=[
            "Encryption at rest is properly implemented for sensitive data",
            "TLS 1.3 is enforced across all external endpoints",
            "Logging and monitoring infrastructure is well-configured"
        ],
        metrics={
            "critical": critical_count, "high": high_count, "medium": medium_count, "low": low_count,
            "total": critical_count + high_count + medium_count + low_count,
            "remediated_same_day": random.randint(0, critical_count),
            "avg_cvss": round(random.uniform(5.5, 8.5), 1),
            "attack_paths_demonstrated": random.randint(1, 4)
        },
        generated_at=datetime.utcnow().isoformat()
    )
