"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.db.database import engine
from src.api.middleware.correlation import CorrelationIdMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.security import RequestLoggingMiddleware, SecurityHeadersMiddleware
from src.api.v1.auth.router import router as auth_router
from src.api.v1.health import router as health_router
from src.api.v1.metrics import router as metrics_router
from src.api.v1.graph.router import router as graph_router
from src.api.v1.investigations.graph_router import router as investigations_graph_router
from src.api.v1.investigations.router import router as investigations_router
from src.api.v1.investigations.websocket import router as ws_router
from src.api.v1.payments.router import router as payments_router
from src.api.v1.admin.router import router as admin_router
from src.api.v1.auth.totp import router as totp_router
from src.api.v1.auth.webauthn import router as webauthn_router
from src.api.v1.auth.sessions import router as sessions_router
from src.api.v1.investigations.report import router as report_router
from src.api.v1.settings.router import router as settings_router
from src.api.v1.settings.webhooks import router as webhooks_router
from src.api.v1.investigations.comments import router as comments_router
from src.api.v1.investigations.summarize import router as summarize_router
from src.api.v1.search import router as search_router
from src.api.v1.workspaces import router as workspaces_router
from src.api.v1.public_api import router as public_api_router
from src.api.v1.playbooks import router as playbooks_router
from src.api.v1.maltego import router as maltego_router
from src.api.v1.search_fulltext import router as search_fulltext_router
from src.api.v1.chat import router as chat_router
from src.api.v1.nl_query import router as nl_query_router
from src.api.v1.watchlist import router as watchlist_router
from src.api.v1.webhook_triggers import router as webhook_triggers_router
from src.api.v1.investigations.fork import router as fork_router
from src.api.v1.playbook_conditions import router as playbook_conditions_router
from src.api.v1.presence import router as presence_router
from src.api.v1.mentions import router as mentions_router
from src.api.v1.report_schedules import router as report_schedules_router
from src.api.v1.report_builder import router as report_builder_router
from src.api.v1.task_board import router as task_board_router
from src.api.v1.templates import router as templates_router
from src.api.v1.integrations import router as integrations_router
from src.api.v1.ticketing import router as ticketing_router
from src.api.v1.graph_analytics import router as graph_analytics_router
from src.api.v1.evidence import router as evidence_router
from src.api.v1.investigation_diff import router as investigation_diff_router
from src.api.v1.saved_searches import router as saved_searches_router
from src.api.v1.lineage import router as lineage_router
from src.api.v1.versioning import router as versioning_router
from src.api.v1.redaction import router as redaction_router
from src.api.v1.report_narrative import router as report_narrative_router
from src.api.v1.email_ingestion import router as email_ingestion_router
from src.api.v1.browser_extension import router as browser_extension_router
from src.api.graphql.router import router as graphql_router
from src.api.v1.api_versions import router as api_versions_router
from src.api.v1.ml import router as ml_router
from src.api.v1.bulk_actions import router as bulk_actions_router
from src.api.v1.campaigns import router as campaigns_router
from src.api.v1.annotations import router as annotations_router
from src.api.v1.scan_profiles import router as scan_profiles_router
from src.api.v1.share_links import router as share_links_router
from src.api.v1.activity_feed import router as activity_feed_router
from src.api.v1.sse import router as sse_router
from src.api.v1.investigation_merge import router as investigation_merge_router
from src.api.v1.tlp import router as tlp_router
from src.api.v1.retention import router as retention_router
from src.api.v1.image_checker.router import router as image_checker_router
from src.api.v1.doc_metadata.router import router as doc_metadata_router
from src.api.v1.email_headers.router import router as email_headers_router
from src.api.v1.mac_lookup.router import router as mac_lookup_router
from src.api.v1.domain_permutation.router import router as domain_permutation_router
from src.api.v1.cloud_exposure.router import router as cloud_exposure_router
from src.api.v1.stealer_logs.router import router as stealer_logs_router
from src.api.v1.supply_chain.router import router as supply_chain_router
from src.api.v1.fediverse.router import router as fediverse_router
from src.api.v1.wigle.router import router as wigle_router
from src.api.v1.tech_recon.router import router as tech_recon_router
from src.api.v1.socmint.router import router as socmint_router
from src.api.v1.credential_intel.router import router as credential_intel_router
from src.api.v1.imint.router import router as imint_router
from src.api.v1.pentesting.router import router as pentesting_router
from src.api.v1.redteam.router import router as redteam_router
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

    # Elasticsearch index setup
    try:
        from src.adapters.search.elasticsearch_store import ElasticsearchStore

        es = ElasticsearchStore()
        await es.ensure_indices()
        app.state.elasticsearch = es
        await log.ainfo("Elasticsearch indices ensured")
    except Exception as exc:
        await log.awarn("Elasticsearch not available", error=str(exc))
        app.state.elasticsearch = None

    # Ensure audit log table is registered with SQLAlchemy metadata
    from src.adapters.db.audit_models import AuditLogModel  # noqa: F401

    yield

    # Shutdown
    await log.ainfo("Shutting down OSINT platform backend")

    if getattr(app.state, "elasticsearch", None) is not None:
        await app.state.elasticsearch.close()

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
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestLoggingMiddleware)

    # Health check and metrics routers
    application.include_router(health_router)
    application.include_router(metrics_router)

    # Routers
    application.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(investigations_router, prefix="/api/v1/investigations", tags=["investigations"])
    application.include_router(ws_router, prefix="/api/v1/investigations", tags=["websocket"])
    application.include_router(investigations_graph_router, prefix="/api/v1/investigations", tags=["graph"])
    application.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
    application.include_router(settings_router, prefix="/api/v1/settings", tags=["settings"])
    application.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])
    application.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
    application.include_router(totp_router, prefix="/api/v1/auth", tags=["2fa"])
    application.include_router(webauthn_router, prefix="/api/v1/auth", tags=["webauthn"])
    application.include_router(sessions_router, prefix="/api/v1/auth", tags=["sessions"])
    application.include_router(report_router, prefix="/api/v1/investigations", tags=["reports"])
    application.include_router(comments_router, prefix="/api/v1/investigations", tags=["comments"])
    application.include_router(webhooks_router, prefix="/api/v1/settings", tags=["webhooks"])
    application.include_router(summarize_router, prefix="/api/v1/investigations", tags=["ai"])
    application.include_router(search_router, prefix="/api/v1", tags=["search"])
    application.include_router(workspaces_router, prefix="/api/v1/workspaces", tags=["workspaces"])
    application.include_router(public_api_router, prefix="/api/v1/public", tags=["public-api"])
    application.include_router(playbooks_router, prefix="/api/v1/playbooks", tags=["playbooks"])
    application.include_router(maltego_router, prefix="/api/v1", tags=["maltego"])
    application.include_router(search_fulltext_router, prefix="/api/v1", tags=["search"])
    application.include_router(chat_router, prefix="/api/v1", tags=["ai"])
    application.include_router(nl_query_router, prefix="/api/v1", tags=["ai"])
    application.include_router(watchlist_router, prefix="/api/v1", tags=["watchlist"])
    application.include_router(webhook_triggers_router, prefix="/api/v1", tags=["webhooks"])
    application.include_router(fork_router, prefix="/api/v1/investigations", tags=["investigations"])
    application.include_router(playbook_conditions_router, prefix="/api/v1", tags=["playbooks"])
    application.include_router(presence_router, prefix="/api/v1", tags=["collaboration"])
    application.include_router(mentions_router, prefix="/api/v1", tags=["collaboration"])
    application.include_router(report_schedules_router, prefix="/api/v1", tags=["reports"])
    application.include_router(report_builder_router, prefix="/api/v1", tags=["reports"])
    application.include_router(task_board_router, prefix="/api/v1", tags=["tasks"])
    application.include_router(templates_router, prefix="/api/v1", tags=["templates"])
    application.include_router(integrations_router, prefix="/api/v1", tags=["integrations"])
    application.include_router(ticketing_router, prefix="/api/v1", tags=["ticketing"])
    application.include_router(graph_analytics_router, prefix="/api/v1", tags=["graph"])
    application.include_router(evidence_router, prefix="/api/v1", tags=["evidence"])
    application.include_router(investigation_diff_router, prefix="/api/v1", tags=["investigations"])
    application.include_router(saved_searches_router, prefix="/api/v1", tags=["saved-searches"])
    application.include_router(lineage_router, prefix="/api/v1", tags=["lineage"])
    application.include_router(versioning_router, prefix="/api/v1", tags=["versioning"])
    application.include_router(redaction_router, prefix="/api/v1", tags=["redaction"])
    application.include_router(report_narrative_router, prefix="/api/v1", tags=["reports"])
    application.include_router(email_ingestion_router, prefix="/api/v1", tags=["ingestion"])
    application.include_router(browser_extension_router, prefix="/api/v1", tags=["extension"])
    application.include_router(graphql_router, prefix="/api", tags=["graphql"])
    application.include_router(api_versions_router, prefix="/api/v1", tags=["api-versions"])
    application.include_router(ml_router, prefix="/api/v1", tags=["ml"])
    application.include_router(bulk_actions_router, prefix="/api/v1", tags=["bulk"])
    application.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["campaigns"])
    application.include_router(annotations_router, prefix="/api/v1", tags=["annotations"])
    application.include_router(scan_profiles_router, prefix="/api/v1/scan-profiles", tags=["scan-profiles"])
    application.include_router(share_links_router, prefix="/api/v1", tags=["share-links"])
    application.include_router(activity_feed_router, prefix="/api/v1", tags=["activity"])
    application.include_router(sse_router, prefix="/api/v1", tags=["streaming"])
    application.include_router(investigation_merge_router, prefix="/api/v1/investigations", tags=["investigations"])
    application.include_router(tlp_router, prefix="/api/v1", tags=["tlp"])
    application.include_router(retention_router, prefix="/api/v1/retention", tags=["retention"])
    application.include_router(image_checker_router, prefix="/api/v1/image-checker", tags=["image-checker"])
    application.include_router(doc_metadata_router, prefix="/api/v1/doc-metadata", tags=["doc-metadata"])
    application.include_router(email_headers_router, prefix="/api/v1/email-headers", tags=["email-headers"])
    application.include_router(mac_lookup_router, prefix="/api/v1/mac-lookup", tags=["mac-lookup"])
    application.include_router(domain_permutation_router, prefix="/api/v1/domain-permutation", tags=["domain-permutation"])
    application.include_router(cloud_exposure_router, prefix="/api/v1/cloud-exposure", tags=["cloud-exposure"])
    application.include_router(stealer_logs_router, prefix="/api/v1/stealer-logs", tags=["stealer-logs"])
    application.include_router(supply_chain_router, prefix="/api/v1/supply-chain", tags=["supply-chain"])
    application.include_router(fediverse_router, prefix="/api/v1/fediverse", tags=["fediverse"])
    application.include_router(wigle_router, prefix="/api/v1/wigle", tags=["wigle"])
    application.include_router(tech_recon_router, prefix="/api/v1/tech-recon", tags=["tech-recon"])
    application.include_router(socmint_router, prefix="/api/v1/socmint", tags=["socmint"])
    application.include_router(credential_intel_router, prefix="/api/v1/credential-intel", tags=["credential-intel"])
    application.include_router(imint_router, prefix="/api/v1/imint", tags=["imint"])
    application.include_router(pentesting_router, prefix="/api/v1/pentesting", tags=["pentesting"])
    application.include_router(redteam_router, prefix="/api/v1/redteam", tags=["red-team"])

    return application


app = create_app()
