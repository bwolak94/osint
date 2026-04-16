"""AI-powered investigation summarization."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.repositories import SqlAlchemyInvestigationRepository
from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class SummaryResponse(BaseModel):
    investigation_id: str
    summary: str
    key_findings: list[str]
    risk_indicators: list[str]
    recommended_actions: list[str]
    scan_recommendations: list[dict]
    risk_score: float


def _generate_summary(investigation, scan_results) -> SummaryResponse:
    """Generate an intelligent summary from scan results without requiring an external LLM.

    Uses rule-based analysis to produce structured intelligence briefs.
    Can be upgraded to use OpenAI/Anthropic API when configured.
    """
    findings = []
    risk_indicators = []
    entities_found = set()
    services_found = set()
    breaches_found = []
    addresses = []
    bank_accounts = []

    for r in scan_results:
        if not r.raw_data or r.raw_data.get("_stub"):
            continue

        rd = r.raw_data

        # VAT/Company data
        if rd.get("name") and rd.get("found"):
            entities_found.add(rd["name"])
            findings.append(f"Entity identified: {rd['name']}")
            if rd.get("status_vat"):
                findings.append(f"VAT status: {rd['status_vat']}")
                if rd["status_vat"] != "Czynny":
                    risk_indicators.append(f"Non-active VAT status: {rd['status_vat']}")
            if rd.get("regon"):
                findings.append(f"REGON: {rd['regon']}")
            if rd.get("working_address"):
                addresses.append(rd["working_address"])
                findings.append(f"Address: {rd['working_address']}")
            if rd.get("bank_accounts"):
                bank_accounts.extend(rd["bank_accounts"])
                findings.append(f"{len(rd['bank_accounts'])} bank account(s) registered")

        # Holehe results
        if rd.get("registered_on") and rd.get("registered_count", 0) > 0:
            svc_list = rd["registered_on"]
            services_found.update(svc_list)
            findings.append(f"Email registered on {len(svc_list)} services: {', '.join(svc_list[:5])}")
            if rd.get("backup_email"):
                findings.append(f"Backup email discovered: {rd['backup_email']}")
                risk_indicators.append("Backup email found — potential for further investigation")
            if rd.get("partial_phone"):
                findings.append(f"Partial phone number recovered: {rd['partial_phone']}")

        # Maigret results
        if rd.get("claimed_count", 0) > 0:
            findings.append(f"Username found on {rd['claimed_count']} platforms")

        # Shodan results
        if rd.get("ports"):
            findings.append(f"Open ports: {', '.join(str(p) for p in rd['ports'][:10])}")
            dangerous_ports = [p for p in rd["ports"] if p in (21, 23, 445, 3389, 5900)]
            if dangerous_ports:
                risk_indicators.append(f"Potentially dangerous open ports: {dangerous_ports}")
            if rd.get("vulns"):
                risk_indicators.append(f"Known vulnerabilities: {', '.join(rd['vulns'][:5])}")

        # GeoIP
        if rd.get("country") and rd.get("city"):
            findings.append(f"IP located in {rd['city']}, {rd['country']}")

        # WHOIS
        if rd.get("registrar"):
            findings.append(f"Domain registered via {rd['registrar']}")
        if rd.get("expiration_date"):
            findings.append(f"Domain expires: {rd['expiration_date']}")

        # DNS
        if rd.get("a_records"):
            findings.append(f"DNS resolves to: {', '.join(rd['a_records'][:3])}")

        # Breaches
        if rd.get("breaches"):
            for b in rd["breaches"]:
                breaches_found.append(b.get("Name", "Unknown"))
            risk_indicators.append(f"Found in {len(rd['breaches'])} data breach(es): {', '.join(breaches_found[:3])}")

    # Scan recommendations based on discovered data
    scan_recommendations = []
    discovered_emails = [
        i for r in scan_results for i in (r.extracted_identifiers or []) if i.startswith("email:")
    ]
    discovered_domains = [
        i for r in scan_results for i in (r.extracted_identifiers or []) if i.startswith("domain:")
    ]
    discovered_ips = [
        i for r in scan_results for i in (r.extracted_identifiers or []) if i.startswith("ip:")
    ]

    if discovered_emails:
        scan_recommendations.append({
            "type": "email",
            "values": [e.split(":", 1)[1] for e in discovered_emails[:3]],
            "scanner": "holehe",
            "reason": "Discovered emails can be checked for service registrations",
        })
    if discovered_domains:
        scan_recommendations.append({
            "type": "domain",
            "values": [d.split(":", 1)[1] for d in discovered_domains[:3]],
            "scanner": "whois",
            "reason": "Discovered domains can be checked for ownership data",
        })
    if discovered_ips:
        scan_recommendations.append({
            "type": "ip_address",
            "values": [i.split(":", 1)[1] for i in discovered_ips[:3]],
            "scanner": "shodan",
            "reason": "Discovered IPs can be checked for open ports and services",
        })

    # Compute risk score (0.0 - 1.0)
    risk_score = 0.0
    if breaches_found:
        risk_score += 0.3
    if risk_indicators:
        risk_score += min(len(risk_indicators) * 0.1, 0.3)
    if len(services_found) > 10:
        risk_score += 0.1
    if bank_accounts:
        risk_score += 0.1
    if any("dangerous" in r.lower() for r in risk_indicators):
        risk_score += 0.2
    risk_score = min(risk_score, 1.0)

    # Build summary
    seed_desc = ", ".join(f"{s.input_type.value}: {s.value}" for s in investigation.seed_inputs)

    summary_parts = [
        f"Investigation \"{investigation.title}\" analyzed {len(investigation.seed_inputs)} seed input(s) ({seed_desc}) "
        f"using {len(scan_results)} scanner(s).",
    ]

    if entities_found:
        summary_parts.append(f"Identified entities: {', '.join(entities_found)}.")
    if services_found:
        summary_parts.append(f"Online presence detected across {len(services_found)} service(s).")
    if bank_accounts:
        summary_parts.append(f"Discovered {len(bank_accounts)} registered bank account(s).")
    if breaches_found:
        summary_parts.append(f"WARNING: Target appears in {len(breaches_found)} known data breach(es).")

    if not findings:
        summary_parts.append("No significant findings were discovered during this scan.")

    recommended = []
    if services_found:
        recommended.append("Review online service registrations for unauthorized accounts")
    if bank_accounts:
        recommended.append("Verify bank accounts against known legitimate accounts")
    if risk_indicators:
        recommended.append("Investigate flagged risk indicators")
    if not recommended:
        recommended.append("No immediate actions required")

    return SummaryResponse(
        investigation_id=str(investigation.id),
        summary=" ".join(summary_parts),
        key_findings=findings[:20],
        risk_indicators=risk_indicators[:10],
        recommended_actions=recommended[:10],
        scan_recommendations=scan_recommendations,
        risk_score=risk_score,
    )


@router.get("/{investigation_id}/summarize", response_model=SummaryResponse)
async def summarize_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SummaryResponse:
    """Generate an AI-powered intelligence summary of an investigation."""
    inv_repo = SqlAlchemyInvestigationRepository(db)
    investigation = await inv_repo.get_by_id(investigation_id)
    if investigation is None or investigation.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Investigation not found")

    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)

    return _generate_summary(investigation, results)
