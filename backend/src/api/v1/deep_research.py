"""Deep Research orchestration API.

Accepts a multi-field person/entity profile and runs all relevant OSINT
modules in parallel, returning a unified result set.

Endpoints:
  POST /api/v1/deep-research/run      — full synchronous run, returns complete result
  GET  /api/v1/deep-research/stream   — SSE stream; yields module events as each completes
"""

from __future__ import annotations

import asyncio
import json
import uuid as _uuid
from typing import Any, AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/deep-research", tags=["deep-research"])

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DeepResearchRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    nip: Optional[str] = None
    company_name: Optional[str] = None


class SocialProfile(BaseModel):
    platform: str
    url: Optional[str]
    found: bool
    username: Optional[str] = None
    followers: Optional[int] = None
    bio: Optional[str] = None


class SocmintResult(BaseModel):
    profiles_found: int
    platforms_checked: int
    social_profiles: list[SocialProfile]
    username_variations: list[str]


class EmailIntelResult(BaseModel):
    email: str
    is_valid: bool
    is_disposable: bool
    breach_count: int
    breach_sources: list[str]
    registered_services: list[str]
    holehe_hits: list[str]
    partial_phone: Optional[str] = None
    backup_email: Optional[str] = None


class PhoneIntelResult(BaseModel):
    phone: str
    country: str
    carrier: str
    line_type: str
    is_valid: bool
    spam_score: int
    breach_count: int
    associated_services: list[str]


class KrsRecord(BaseModel):
    krs_number: Optional[str]
    nip: Optional[str]
    regon: Optional[str]
    company_name: str
    status: str
    registration_date: Optional[str]
    address: Optional[str]
    board_members: list[str]
    share_capital: Optional[str]


class CorporateResult(BaseModel):
    krs_records: list[KrsRecord]
    ceidg_found: bool
    regon_data: Optional[dict[str, str]]
    company_name: Optional[str]
    related_entities: list[str]


class DarkWebResult(BaseModel):
    leaks_found: int
    paste_hits: int
    forum_mentions: int
    marketplaces_seen: list[str]
    sample_records: list[dict[str, str]]


class RelationEdge(BaseModel):
    source: str
    target: str
    relation: str
    confidence: float


class RelationsGraph(BaseModel):
    nodes: list[dict[str, str]]
    edges: list[RelationEdge]


class AiSynthesis(BaseModel):
    summary: str
    key_findings: list[str]
    risk_level: str
    confidence: float
    recommended_pivots: list[str]


class DeepResearchResult(BaseModel):
    request_id: str
    target_label: str
    socmint: Optional[SocmintResult] = None
    email_intel: Optional[EmailIntelResult] = None
    phone_intel: Optional[PhoneIntelResult] = None
    corporate: Optional[CorporateResult] = None
    dark_web: Optional[DarkWebResult] = None
    relations_graph: RelationsGraph
    ai_synthesis: AiSynthesis
    modules_run: list[str]
    total_findings: int


# ---------------------------------------------------------------------------
# Real scanner helpers — each tries the real scanner, falls back to stub
# ---------------------------------------------------------------------------


async def _run_socmint(req: DeepResearchRequest, queue: asyncio.Queue[dict[str, Any]] | None = None) -> SocmintResult:
    """Run Sherlock + Maigret for username enumeration."""
    username = req.username or (
        f"{req.first_name.lower()}{req.last_name.lower()}"
        if req.first_name and req.last_name
        else None
    )
    if not username:
        return SocmintResult(profiles_found=0, platforms_checked=0,
                             social_profiles=[], username_variations=[])

    if queue:
        await queue.put({"module": "SOCMINT", "status": "running",
                         "message": f"Scanning {username} across platforms…"})

    # Try Sherlock scanner (HTTP-based, no external lib required)
    try:
        from src.adapters.scanners.sherlock_scanner import SherlockScanner
        from src.core.domain.entities.types import ScanInputType

        scanner = SherlockScanner()
        result = await scanner._do_scan(username, ScanInputType.USERNAME)

        profiles_data: list[dict[str, Any]] = result.get("profiles", [])
        profiles = [
            SocialProfile(
                platform=p.get("site", ""),
                url=p.get("url"),
                found=True,
                username=username,
            )
            for p in profiles_data
        ]
        checked = result.get("total_checked", len(profiles))

    except Exception as e:
        log.warning("sherlock scanner failed, using HTTP fallback", error=str(e))
        # Fallback: direct HTTP probing against common platforms
        from src.adapters.scanners.sherlock_scanner import SherlockScanner, SITES
        import httpx

        found_profiles: list[SocialProfile] = []
        async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
            async def _probe(name: str, url_tpl: str) -> SocialProfile:
                url = url_tpl.format(username=username)
                try:
                    r = await client.get(url)
                    found = r.status_code == 200
                except Exception:
                    found = False
                return SocialProfile(platform=name, url=url if found else None, found=found, username=username if found else None)

            tasks = [_probe(name, tpl) for name, tpl in list(SITES.items())[:20]]
            found_profiles = list(await asyncio.gather(*tasks))

        profiles = found_profiles
        checked = len(profiles)

    found_count = sum(1 for p in profiles if p.found)

    # Also attempt Maigret for extended coverage
    maigret_extra: list[SocialProfile] = []
    try:
        from src.adapters.scanners.maigret_scanner import MaigretScanner
        from src.core.domain.entities.types import ScanInputType

        m_scanner = MaigretScanner()
        m_result = await asyncio.wait_for(
            m_scanner._do_scan(username, ScanInputType.USERNAME), timeout=60
        )
        existing_platforms = {p.platform.lower() for p in profiles}
        for claim in m_result.get("claimed_profiles", []):
            site = claim.get("site", "")
            if site.lower() not in existing_platforms:
                maigret_extra.append(SocialProfile(
                    platform=site,
                    url=claim.get("url"),
                    found=True,
                    username=username,
                ))
    except Exception as e:
        log.info("maigret not available or timed out", error=str(e))

    all_profiles = profiles + maigret_extra
    total_found = sum(1 for p in all_profiles if p.found)

    variations = [username, f"{username}_", f"{username}1", f"_{username}", f"{username}.official"]

    if queue:
        await queue.put({"module": "SOCMINT", "status": "done",
                         "message": f"Found {total_found} profiles across {len(all_profiles)} platforms"})

    return SocmintResult(
        profiles_found=total_found,
        platforms_checked=len(all_profiles),
        social_profiles=all_profiles,
        username_variations=variations,
    )


async def _run_email_intel(email: str, queue: asyncio.Queue[dict[str, Any]] | None = None) -> EmailIntelResult:
    """Run Holehe + HIBP breach scanner."""
    if queue:
        await queue.put({"module": "Email Intel", "status": "running",
                         "message": f"Checking {email} via Holehe + HIBP…"})

    # Holehe — registered services check
    holehe_hits: list[str] = []
    registered: list[str] = []
    partial_phone: str | None = None
    backup_email: str | None = None
    try:
        from src.adapters.scanners.holehe_scanner import HoleheScanner
        from src.core.domain.entities.types import ScanInputType

        h_scanner = HoleheScanner()
        h_result = await h_scanner._do_scan(email, ScanInputType.EMAIL)
        registered = h_result.get("registered_on", [])
        holehe_hits = registered[:5]  # top hits
        partial_phone = h_result.get("partial_phone")
        backup_email = h_result.get("backup_email")
    except Exception as e:
        log.info("holehe unavailable", error=str(e))

    # HIBP breach check
    breach_sources: list[str] = []
    try:
        from src.adapters.scanners.breach_scanner import BreachScanner
        from src.core.domain.entities.types import ScanInputType

        b_scanner = BreachScanner()
        b_result = await b_scanner._do_scan(email, ScanInputType.EMAIL)
        breach_sources = [b.get("Name", b.get("name", "")) for b in b_result.get("breaches", [])]
    except Exception as e:
        log.info("breach scanner unavailable", error=str(e))

    if queue:
        await queue.put({"module": "Email Intel", "status": "done",
                         "message": f"{len(registered)} services, {len(breach_sources)} breaches"})

    return EmailIntelResult(
        email=email,
        is_valid=True,
        is_disposable=False,
        breach_count=len(breach_sources),
        breach_sources=breach_sources,
        registered_services=registered,
        holehe_hits=holehe_hits,
        **({"partial_phone": partial_phone} if partial_phone else {}),
        **({"backup_email": backup_email} if backup_email else {}),
    )


async def _run_phone_intel(phone: str, queue: asyncio.Queue[dict[str, Any]] | None = None) -> PhoneIntelResult:
    """Run phonenumbers + Ignorant scanner."""
    if queue:
        await queue.put({"module": "Phone Intel", "status": "running",
                         "message": f"Looking up {phone}…"})

    country = "Unknown"
    carrier_name = "Unknown"
    line_type = "unknown"
    is_valid = False
    associated: list[str] = []

    try:
        from src.adapters.scanners.phone_scanner import PhoneScanner
        from src.core.domain.entities.types import ScanInputType

        p_scanner = PhoneScanner()
        p_result = await p_scanner._do_scan(phone, ScanInputType.PHONE)
        country = p_result.get("country", "Unknown")
        carrier_name = p_result.get("carrier", "Unknown")
        line_type = p_result.get("line_type", "unknown")
        is_valid = p_result.get("is_valid", False)
    except Exception as e:
        log.info("phone scanner unavailable", error=str(e))

    # Ignorant — check social platforms
    try:
        from src.adapters.scanners.ignorant_scanner import IgnorantScanner
        from src.core.domain.entities.types import ScanInputType

        i_scanner = IgnorantScanner()
        i_result = await i_scanner._do_scan(phone, ScanInputType.PHONE)
        platform_results: dict[str, str] = i_result.get("platforms", {})
        associated = [p for p, status in platform_results.items() if status == "registered"]
    except Exception as e:
        log.info("ignorant scanner unavailable", error=str(e))

    if queue:
        await queue.put({"module": "Phone Intel", "status": "done",
                         "message": f"{country} · {carrier_name} · {len(associated)} services"})

    return PhoneIntelResult(
        phone=phone,
        country=country,
        carrier=carrier_name,
        line_type=line_type,
        is_valid=is_valid,
        spam_score=0,
        breach_count=0,
        associated_services=associated,
    )


async def _run_krs(
    nip: str | None,
    company_name: str | None,
    queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> CorporateResult:
    """Run KRS + CEIDG scrapers via Playwright."""
    if queue:
        await queue.put({"module": "KRS / CEIDG", "status": "running",
                         "message": "Querying Polish business registries…"})

    krs_records: list[KrsRecord] = []
    ceidg_found = False

    # KRS via Playwright
    if nip or company_name:
        try:
            from src.adapters.scanners.playwright_krs import PlaywrightKRSScanner
            from src.core.domain.entities.types import ScanInputType

            krs_scanner = PlaywrightKRSScanner()
            input_val = nip or company_name or ""
            input_type = ScanInputType.NIP if nip else ScanInputType.DOMAIN
            krs_result = await asyncio.wait_for(
                krs_scanner._do_scan(input_val, input_type), timeout=45
            )

            if krs_result.get("found") and krs_result.get("results"):
                # Parse raw table rows into KrsRecord
                for row in krs_result["results"][:3]:
                    cells = [str(c).strip() for c in row if c]
                    if cells:
                        krs_records.append(KrsRecord(
                            krs_number=cells[0] if len(cells) > 0 else None,
                            nip=nip,
                            regon=None,
                            company_name=cells[1] if len(cells) > 1 else (company_name or ""),
                            status=cells[2] if len(cells) > 2 else "ACTIVE",
                            registration_date=cells[3] if len(cells) > 3 else None,
                            address=cells[4] if len(cells) > 4 else None,
                            board_members=[],
                            share_capital=None,
                        ))
        except Exception as e:
            log.info("KRS playwright scanner unavailable or timed out", error=str(e))

    # CEIDG check
    if nip:
        try:
            from src.adapters.scanners.playwright_ceidg import PlaywrightCEIDGScanner
            from src.core.domain.entities.types import ScanInputType

            ceidg_scanner = PlaywrightCEIDGScanner()
            ceidg_result = await asyncio.wait_for(
                ceidg_scanner._do_scan(nip, ScanInputType.NIP), timeout=45
            )
            ceidg_found = ceidg_result.get("found", False)
        except Exception as e:
            log.info("CEIDG scanner unavailable or timed out", error=str(e))

    if queue:
        await queue.put({"module": "KRS / CEIDG", "status": "done",
                         "message": f"{len(krs_records)} KRS record(s), CEIDG: {'yes' if ceidg_found else 'no'}"})

    return CorporateResult(
        krs_records=krs_records,
        ceidg_found=ceidg_found,
        regon_data=None,
        company_name=(krs_records[0].company_name if krs_records else company_name),
        related_entities=[],
    )


async def _run_dark_web(
    target: str,
    queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> DarkWebResult:
    """Run dark web + paste site scanners."""
    if queue:
        await queue.put({"module": "Dark Web", "status": "running",
                         "message": f"Searching dark web & paste sites for {target}…"})

    forum_mentions = 0
    marketplaces: list[str] = []

    # Ahmia dark web search
    try:
        from src.adapters.scanners.darkweb_scanner import DarkWebScanner
        from src.core.domain.entities.types import ScanInputType

        dw_scanner = DarkWebScanner()
        input_type = ScanInputType.EMAIL if "@" in target else ScanInputType.USERNAME
        dw_result = await dw_scanner._do_scan(target, input_type)
        forum_mentions = dw_result.get("mention_count", 0)
    except Exception as e:
        log.info("dark web scanner unavailable", error=str(e))

    # Paste sites
    paste_count = 0
    sample_records: list[dict[str, str]] = []
    try:
        from src.adapters.scanners.paste_scanner import PasteSitesScanner
        from src.core.domain.entities.types import ScanInputType

        paste_scanner = PasteSitesScanner()
        input_type = ScanInputType.EMAIL if "@" in target else ScanInputType.USERNAME
        paste_result = await paste_scanner._do_scan(target, input_type)
        paste_count = paste_result.get("paste_count", 0)
        for p in paste_result.get("pastes", [])[:2]:
            sample_records.append({
                "source": "pastebin",
                "id": str(p.get("id", "")),
                "date": str(p.get("date", "")),
            })
    except Exception as e:
        log.info("paste scanner unavailable", error=str(e))

    if queue:
        await queue.put({"module": "Dark Web", "status": "done",
                         "message": f"{forum_mentions} mentions, {paste_count} paste hits"})

    return DarkWebResult(
        leaks_found=1 if forum_mentions > 5 else 0,
        paste_hits=paste_count,
        forum_mentions=forum_mentions,
        marketplaces_seen=marketplaces,
        sample_records=sample_records,
    )


# ---------------------------------------------------------------------------
# Graph + Synthesis builders
# ---------------------------------------------------------------------------


def _build_graph(req: DeepResearchRequest, socmint: SocmintResult | None) -> RelationsGraph:
    nodes: list[dict[str, str]] = []
    edges: list[RelationEdge] = []

    person_label = " ".join(filter(None, [req.first_name, req.last_name])) or req.username or "Target"
    nodes.append({"id": "person", "label": person_label, "type": "person"})

    if req.email:
        nodes.append({"id": "email", "label": req.email, "type": "email"})
        edges.append(RelationEdge(source="person", target="email", relation="owns", confidence=0.99))

    if req.phone:
        nodes.append({"id": "phone", "label": req.phone, "type": "phone"})
        edges.append(RelationEdge(source="person", target="phone", relation="owns", confidence=0.95))

    if req.username:
        nodes.append({"id": "username", "label": req.username, "type": "username"})
        edges.append(RelationEdge(source="person", target="username", relation="uses", confidence=0.9))

    if socmint:
        for p in socmint.social_profiles:
            if p.found:
                nid = f"platform_{p.platform}"
                nodes.append({"id": nid, "label": p.platform, "type": "online_service"})
                src = "username" if req.username else "person"
                edges.append(RelationEdge(source=src, target=nid, relation="profile_on", confidence=0.85))

    return RelationsGraph(nodes=nodes, edges=edges)


def _build_synthesis(
    req: DeepResearchRequest,
    socmint: SocmintResult | None,
    email: EmailIntelResult | None,
    phone: PhoneIntelResult | None,
    corporate: CorporateResult | None,
    dark_web: DarkWebResult | None,
) -> AiSynthesis:
    person = " ".join(filter(None, [req.first_name, req.last_name])) or req.username or "the target"
    findings: list[str] = []
    risk_score = 0

    if socmint and socmint.profiles_found > 5:
        findings.append(f"High social media presence: {socmint.profiles_found} profiles across {socmint.platforms_checked} platforms")
        risk_score += 20
    elif socmint and socmint.profiles_found > 0:
        findings.append(f"Social media presence: {socmint.profiles_found} profiles found")
        risk_score += 10

    if email and email.breach_count > 0:
        findings.append(f"Email compromised in {email.breach_count} breach(es): {', '.join(email.breach_sources[:3])}")
        risk_score += 30

    if email and email.registered_services:
        findings.append(f"Email registered on {len(email.registered_services)} online services (Holehe: {', '.join(email.holehe_hits[:3])})")
        risk_score += 10

    if dark_web and (dark_web.leaks_found > 0 or dark_web.paste_hits > 0 or dark_web.forum_mentions > 10):
        findings.append(f"Dark web exposure: {dark_web.leaks_found} leaks, {dark_web.paste_hits} paste hits, {dark_web.forum_mentions} mentions")
        risk_score += 35

    if corporate and corporate.krs_records:
        krs = corporate.krs_records[0]
        findings.append(f"Registered company: {krs.company_name} (KRS {krs.krs_number or 'n/a'}, status: {krs.status})")
        risk_score += 10

    if not findings:
        findings.append(f"No significant risk indicators found for {person}")

    risk_level = "critical" if risk_score >= 70 else "high" if risk_score >= 45 else "medium" if risk_score >= 20 else "low"
    confidence = min(0.95, 0.45 + (len(findings) * 0.08))

    pivots: list[str] = []
    if email and email.holehe_hits:
        pivots.append(f"Investigate accounts on: {', '.join(email.holehe_hits)}")
    if email and email.partial_phone:
        pivots.append(f"Partial phone recovered from account: {email.partial_phone}")
    if email and email.backup_email:
        pivots.append(f"Backup email found: {email.backup_email}")
    if socmint and socmint.username_variations:
        pivots.append("Cross-correlate username variations across additional platforms")
    if dark_web and (dark_web.paste_hits > 0 or dark_web.leaks_found > 0):
        pivots.append("Search breach databases for leaked credentials")

    return AiSynthesis(
        summary=f"Deep research on {person} reveals {len(findings)} significant finding(s). "
                f"Overall risk is assessed as {risk_level.upper()}.",
        key_findings=findings,
        risk_level=risk_level,
        confidence=round(confidence, 2),
        recommended_pivots=pivots,
    )


# ---------------------------------------------------------------------------
# Shared orchestration logic
# ---------------------------------------------------------------------------


async def _orchestrate(
    req: DeepResearchRequest,
    queue: asyncio.Queue[dict[str, Any]] | None = None,
) -> DeepResearchResult:
    request_id = str(_uuid.uuid4())
    modules_run: list[str] = []
    task_map: dict[str, asyncio.Task[Any]] = {}

    if req.username or (req.first_name and req.last_name):
        task_map["socmint"] = asyncio.create_task(_run_socmint(req, queue))
        modules_run.append("SOCMINT / Platform Enumeration")

    if req.email:
        task_map["email"] = asyncio.create_task(_run_email_intel(req.email, queue))
        modules_run.append("Email Intelligence (Holehe)")

    if req.phone:
        task_map["phone"] = asyncio.create_task(_run_phone_intel(req.phone, queue))
        modules_run.append("Phone Intelligence")

    if req.nip or req.company_name:
        task_map["corporate"] = asyncio.create_task(_run_krs(req.nip, req.company_name, queue))
        modules_run.append("KRS / CEIDG / REGON")

    dark_target = req.email or req.username or f"{req.first_name or ''} {req.last_name or ''}".strip()
    if dark_target:
        task_map["dark_web"] = asyncio.create_task(_run_dark_web(dark_target, queue))
        modules_run.append("Dark Web & Leaks")

    await asyncio.gather(*task_map.values(), return_exceptions=True)

    socmint_res: SocmintResult | None = _safe_result(task_map, "socmint")
    email_res: EmailIntelResult | None = _safe_result(task_map, "email")
    phone_res: PhoneIntelResult | None = _safe_result(task_map, "phone")
    corp_res: CorporateResult | None = _safe_result(task_map, "corporate")
    dark_res: DarkWebResult | None = _safe_result(task_map, "dark_web")

    graph = _build_graph(req, socmint_res)
    synthesis = _build_synthesis(req, socmint_res, email_res, phone_res, corp_res, dark_res)

    total = (
        (socmint_res.profiles_found if socmint_res else 0)
        + (email_res.breach_count if email_res else 0)
        + (dark_res.leaks_found + dark_res.paste_hits if dark_res else 0)
        + (len(corp_res.krs_records) if corp_res else 0)
    )

    target_label = (
        " ".join(filter(None, [req.first_name, req.last_name]))
        or req.username
        or req.email
        or req.company_name
        or "Unknown Target"
    )

    return DeepResearchResult(
        request_id=request_id,
        target_label=target_label,
        socmint=socmint_res,
        email_intel=email_res,
        phone_intel=phone_res,
        corporate=corp_res,
        dark_web=dark_res,
        relations_graph=graph,
        ai_synthesis=synthesis,
        modules_run=modules_run,
        total_findings=total,
    )


def _safe_result(task_map: dict[str, asyncio.Task[Any]], key: str) -> Any:
    task = task_map.get(key)
    if task is None:
        return None
    exc = task.exception() if not task.cancelled() else None
    if exc:
        log.warning("module task failed", module=key, error=str(exc))
        return None
    return task.result()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/run", response_model=DeepResearchResult)
async def run_deep_research(req: DeepResearchRequest) -> DeepResearchResult:
    """Orchestrate all applicable OSINT modules for a given subject."""
    return await _orchestrate(req)


@router.get("/stream")
async def stream_deep_research(
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    nip: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
) -> StreamingResponse:
    """SSE stream — yields module progress events then the final complete result."""
    req = DeepResearchRequest(
        first_name=first_name, last_name=last_name, email=email,
        username=username, phone=phone, nip=nip, company_name=company_name,
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Run orchestration in background, posting events to queue
        orch_task = asyncio.create_task(_orchestrate(req, queue))

        # Stream events until orchestration completes
        while not orch_task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"event: module\ndata: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield "data: ping\n\n"

        # Drain remaining queued events
        while not queue.empty():
            event = queue.get_nowait()
            yield f"event: module\ndata: {json.dumps(event)}\n\n"

        # Emit the final result
        exc = orch_task.exception() if not orch_task.cancelled() else None
        if exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        else:
            result = orch_task.result()
            yield f"event: complete\ndata: {result.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
