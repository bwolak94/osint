"""Health check endpoints for load balancers and monitoring."""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Check connectivity to all backing services."""
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        from src.adapters.db.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {type(e).__name__}"

    # Redis
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis:
            await redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not configured"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"

    # Neo4j
    try:
        from src.config import get_settings
        from neo4j import AsyncGraphDatabase
        settings = get_settings()
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=30.0,
            max_transaction_retry_time=30.0,
        )
        async with driver.session() as session:
            await session.run("RETURN 1")
        await driver.close()
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {type(e).__name__}"

    # n8n connectivity (#39)
    try:
        import httpx as _httpx
        import os as _os
        n8n_url = _os.getenv("N8N_BASE_URL", "http://n8n:5678")
        async with _httpx.AsyncClient(timeout=3) as _client:
            r = await _client.get(f"{n8n_url}/healthz")
            checks["n8n"] = "ok" if r.status_code < 500 else f"http_{r.status_code}"
    except Exception as e:
        checks["n8n"] = f"unreachable: {type(e).__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )
