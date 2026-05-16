"""Scanner benchmark endpoint — run a test scan and measure latency.

POST /api/v1/scanners/benchmark
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["benchmark"])

_BENCHMARK_TIMEOUT = 10.0


class BenchmarkRequest(BaseModel):
    scanner_name: str
    test_input: str
    input_type: str = "domain"


class BenchmarkResponse(BaseModel):
    scanner_name: str
    test_input: str
    latency_ms: float
    finding_count: int
    success: bool
    error: str | None
    cache_hit: bool


@router.post("/scanners/benchmark", response_model=BenchmarkResponse)
async def benchmark_scanner(
    body: BenchmarkRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> BenchmarkResponse:
    """Run a test scan with timing measurement. 10-second wall-clock timeout enforced."""
    from src.adapters.scanners.registry import get_default_registry
    from src.core.domain.entities.types import ScanInputType

    try:
        registry = get_default_registry()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Scanner registry unavailable") from exc

    try:
        input_type_enum = ScanInputType(body.input_type)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown input_type '{body.input_type}'. Valid values: {[e.value for e in ScanInputType]}",
        )

    scanner = None
    if hasattr(registry, "_scanners"):
        scanner = registry._scanners.get(body.scanner_name)
    if scanner is None:
        try:
            scanner = registry.get_scanner(body.scanner_name)
        except Exception:
            pass
    if scanner is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scanner '{body.scanner_name}' not found in registry",
        )

    t0 = time.perf_counter()
    finding_count = 0
    success = False
    error_msg: str | None = None
    cache_hit = False

    try:
        result = await asyncio.wait_for(
            scanner.scan(body.test_input, input_type_enum),
            timeout=_BENCHMARK_TIMEOUT,
        )
        findings = result.get("findings", []) if isinstance(result, dict) else []
        finding_count = len(findings)
        cache_hit = bool(result.get("cache_hit", False)) if isinstance(result, dict) else False
        success = True
    except asyncio.TimeoutError:
        error_msg = f"Scan timed out after {_BENCHMARK_TIMEOUT}s"
    except Exception as exc:
        error_msg = str(exc)

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    return BenchmarkResponse(
        scanner_name=body.scanner_name,
        test_input=body.test_input,
        latency_ms=latency_ms,
        finding_count=finding_count,
        success=success,
        error=error_msg,
        cache_hit=cache_hit,
    )
