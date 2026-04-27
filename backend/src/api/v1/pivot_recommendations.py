"""AI-powered pivot recommendation engine.

Analyses the current investigation graph state (scanners run, identifiers
discovered) and asks the configured LLM to suggest the 3-5 most valuable
next investigative steps.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import async_session_factory
from src.adapters.db.models import IdentityModel, InvestigationModel, ScanResultModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

router = APIRouter()


class PivotRecommendation(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "scanner": "shodan_scanner",
        "reason": "IP 1.2.3.4 has open port 22 suggesting SSH brute-force risk.",
        "target": "1.2.3.4",
        "confidence": "high",
    }}}

    scanner: str
    reason: str
    target: str
    confidence: str  # "high" | "medium" | "low"


class PivotRecommendationsResponse(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "investigation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "recommendations": [{"scanner": "shodan_scanner", "reason": "Open SSH port.", "target": "1.2.3.4", "confidence": "high"}],
        "summary": "Focus on network exposure via Shodan and credential leaks via HIBP.",
    }}}

    investigation_id: str
    recommendations: list[PivotRecommendation]
    summary: str


_SYSTEM_PROMPT = """You are an OSINT investigation expert.
Given the current state of an investigation, suggest the 3-5 most valuable
next investigative pivots. For each pivot, specify:
- scanner: the scanner module name to run next
- reason: why this pivot is valuable
- target: the specific identifier to investigate
- confidence: "high", "medium", or "low"

Respond ONLY as a JSON object with keys:
  recommendations: list of {scanner, reason, target, confidence}
  summary: one sentence overview of the recommended investigation path
"""


def _build_context(
    investigation: InvestigationModel,
    identities: list[IdentityModel],
    scan_results: list[ScanResultModel],
) -> str:
    scanners_run = sorted({r.scanner_name for r in scan_results})
    discovered_emails = sorted({e for i in identities for e in i.emails})
    discovered_usernames = sorted({u for i in identities for u in i.usernames})
    discovered_domains = [
        idf for r in scan_results
        for idf in r.extracted_identifiers
        if "." in idf and not idf.startswith("@")
    ][:10]

    return (
        f"Investigation: {investigation.title}\n"
        f"Seed inputs: {investigation.seed_inputs}\n"
        f"Scanners already run: {', '.join(scanners_run) or 'none'}\n"
        f"Discovered emails: {', '.join(discovered_emails[:10]) or 'none'}\n"
        f"Discovered usernames: {', '.join(discovered_usernames[:10]) or 'none'}\n"
        f"Discovered domains: {', '.join(discovered_domains) or 'none'}\n"
        f"Total identities resolved: {len(identities)}\n"
        f"Total scan results: {len(scan_results)}\n"
    )


async def _call_llm(context: str) -> dict[str, Any]:
    """Call the configured LLM and parse the JSON response.

    Retries up to 3 times on transient errors (429, 500, 503) with
    exponential backoff via tenacity before raising to the caller.
    """
    import json

    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    from src.config import get_settings

    settings = get_settings()

    async def _invoke() -> str:
        if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            try:
                msg = await client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=1024,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": context}],
                )
                return msg.content[0].text
            except anthropic.BadRequestError:
                # Content policy / prompt issue — do not retry
                return "{}"
            except anthropic.APIStatusError as exc:
                if exc.status_code in (429, 500, 503):
                    raise  # tenacity will retry
                return "{}"
        else:
            from openai import AsyncOpenAI, APIStatusError

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            try:
                resp = await client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": context},
                    ],
                    max_tokens=1024,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content or "{}"
            except APIStatusError as exc:
                if exc.status_code in (429, 500, 503):
                    raise  # tenacity will retry
                return "{}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=False,
    )
    async def _invoke_with_retry() -> str:
        return await _invoke()

    try:
        raw = await _invoke_with_retry() or "{}"
    except Exception:
        # All retries exhausted — return empty recommendations (never expose raw error)
        return {"recommendations": [], "summary": "AI recommendations temporarily unavailable."}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"recommendations": [], "summary": "Unable to parse LLM response."}


def _graph_hash(scan_results: list[ScanResultModel]) -> str:
    """Stable hash of the current investigation graph state.

    The cache key is scoped to (investigation_id, graph_hash) so that
    recommendations are invalidated whenever new scan results appear.
    """
    import hashlib

    payload = "|".join(
        sorted(f"{r.scanner_name}:{r.input_value}:{r.status}" for r in scan_results)
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


_PIVOT_CACHE_TTL = 3600  # 1 hour


@router.get(
    "/investigations/{investigation_id}/pivot-recommendations",
    response_model=PivotRecommendationsResponse,
    tags=["pivot-recommendations"],
)
async def get_pivot_recommendations(
    investigation_id: str,
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> PivotRecommendationsResponse:
    """Return AI-generated pivot recommendations for the next investigation steps.

    Results are cached in Redis keyed by (investigation_id, graph_hash) with
    a 1-hour TTL.  Set force_refresh=true to bypass the cache.
    """
    import json

    import redis.asyncio as aioredis

    from src.config import get_settings

    settings = get_settings()
    inv_id = uuid.UUID(investigation_id)

    inv = (
        await db.execute(select(InvestigationModel).where(InvestigationModel.id == inv_id))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    identities = (
        await db.execute(select(IdentityModel).where(IdentityModel.investigation_id == inv_id))
    ).scalars().all()

    scan_results = (
        await db.execute(select(ScanResultModel).where(ScanResultModel.investigation_id == inv_id))
    ).scalars().all()
    scan_results_list = list(scan_results)

    # Cache lookup
    graph_hash = _graph_hash(scan_results_list)
    cache_key = f"pivot_recs:{investigation_id}:{graph_hash}"

    redis_client: aioredis.Redis | None = None
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        if not force_refresh:
            cached = await redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                return PivotRecommendationsResponse(
                    investigation_id=investigation_id,
                    recommendations=[PivotRecommendation(**r) for r in data.get("recommendations", [])],
                    summary=data.get("summary", ""),
                )
    except Exception:
        redis_client = None  # Redis unavailable — proceed without cache

    context = _build_context(inv, list(identities), scan_results_list)
    llm_result = await _call_llm(context)

    recommendations = [
        PivotRecommendation(**r)
        for r in llm_result.get("recommendations", [])
        if all(k in r for k in ("scanner", "reason", "target", "confidence"))
    ]

    response = PivotRecommendationsResponse(
        investigation_id=investigation_id,
        recommendations=recommendations,
        summary=llm_result.get("summary", ""),
    )

    # Store in cache
    if redis_client is not None:
        try:
            await redis_client.set(
                cache_key,
                json.dumps({"recommendations": [r.model_dump() for r in recommendations], "summary": response.summary}),
                ex=_PIVOT_CACHE_TTL,
            )
        except Exception:
            pass
        finally:
            await redis_client.aclose()

    return response
