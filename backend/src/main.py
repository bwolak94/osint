"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.db.database import engine
from src.api.middleware.correlation import CorrelationIdMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.v1.auth.router import router as auth_router
from src.api.v1.graph.router import router as graph_router
from src.api.v1.investigations.graph_router import router as investigations_graph_router
from src.api.v1.investigations.router import router as investigations_router
from src.api.v1.investigations.websocket import router as ws_router
from src.api.v1.payments.router import router as payments_router
from src.api.v1.settings.router import router as settings_router
from src.config import get_settings


def configure_logging() -> None:
    """Initialize structured logging with structlog."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    log = structlog.get_logger()

    # Startup
    await log.ainfo("Starting OSINT platform backend")

    # Database pool is initialized lazily by SQLAlchemy on first use.
    # Redis connection for rate limiting / caching.
    settings = get_settings()
    try:
        import redis.asyncio as aioredis

        app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await app.state.redis.ping()
        await log.ainfo("Redis connection established")
    except Exception as exc:
        await log.awarn("Redis not available, rate limiting disabled", error=str(exc))
        app.state.redis = None

    yield

    # Shutdown
    await log.ainfo("Shutting down OSINT platform backend")

    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.close()

    await engine.dispose()
    await log.ainfo("Database pool disposed")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Middleware (order matters: outermost first)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(RateLimitMiddleware)

    # Health check
    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Routers
    application.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(investigations_router, prefix="/api/v1/investigations", tags=["investigations"])
    application.include_router(ws_router, prefix="/api/v1/investigations", tags=["websocket"])
    application.include_router(investigations_graph_router, prefix="/api/v1/investigations", tags=["graph"])
    application.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
    application.include_router(settings_router, prefix="/api/v1/settings", tags=["settings"])
    application.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])

    return application


app = create_app()
