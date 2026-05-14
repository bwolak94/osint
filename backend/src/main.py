"""FastAPI application entry point."""

import importlib
import pkgutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.adapters.db.database import engine
from src.api.middleware.correlation import CorrelationIdMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.security import RequestLoggingMiddleware, SecurityHeadersMiddleware
from src.config import get_settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Router auto-discovery
# ---------------------------------------------------------------------------

_ROUTER_REGISTRY: list[tuple[str, str, str, list[str]]] = [
    # (module_path, attr_name, prefix, tags)

    # ── Infrastructure ────────────────────────────────────────────────────────
    ("src.api.v1.health", "router", "/health", ["health"]),
    ("src.api.v1.metrics", "router", "/metrics", ["metrics"]),

    # ── Auth & sessions ───────────────────────────────────────────────────────
    ("src.api.v1.auth.router", "router", "/api/v1/auth", ["auth"]),
    ("src.api.v1.investigations.router", "router", "/api/v1/investigations", ["investigations"]),
    ("src.api.v1.investigations.websocket", "router", "/api/v1/investigations", ["websocket"]),
    ("src.api.v1.investigations.graph_router", "router", "/api/v1/investigations", ["graph"]),
    ("src.api.v1.graph.router", "router", "/api/v1/graph", ["graph"]),
    ("src.api.v1.settings.router", "router", "/api/v1/settings", ["settings"]),
    ("src.api.v1.payments.router", "router", "/api/v1/payments", ["payments"]),
    ("src.api.v1.admin.router", "router", "/api/v1/admin", ["admin"]),
    ("src.api.v1.auth.totp", "router", "/api/v1/auth", ["2fa"]),
    ("src.api.v1.auth.webauthn", "router", "/api/v1/auth", ["webauthn"]),
    ("src.api.v1.auth.sessions", "router", "/api/v1/auth", ["sessions"]),
    ("src.api.v1.auth.tos", "router", "/api/v1/auth", ["auth-tos"]),
    ("src.api.v1.auth.sso", "router", "/api/v1", ["sso"]),

    # ── Investigations ────────────────────────────────────────────────────────
    ("src.api.v1.investigations.report", "router", "/api/v1/investigations", ["reports"]),
    ("src.api.v1.investigations.comments", "router", "/api/v1/investigations", ["comments"]),
    ("src.api.v1.investigations.fork", "router", "/api/v1/investigations", ["investigations"]),
    ("src.api.v1.investigations.summarize", "router", "/api/v1/investigations", ["ai"]),
    ("src.api.v1.settings.webhooks", "router", "/api/v1/settings", ["webhooks"]),
    # ── Core platform ─────────────────────────────────────────────────────────
    ("src.api.v1.search", "router", "/api/v1", ["search"]),
    ("src.api.v1.search_fulltext", "router", "/api/v1", ["search"]),
    ("src.api.v1.workspaces", "router", "/api/v1/workspaces", ["workspaces"]),
    ("src.api.v1.public_api", "router", "/api/v1/public", ["public-api"]),
    ("src.api.v1.playbooks", "router", "/api/v1/playbooks", ["playbooks"]),
    ("src.api.v1.playbook_conditions", "router", "/api/v1", ["playbooks"]),
    ("src.api.v1.maltego", "router", "/api/v1", ["maltego"]),
    ("src.api.v1.chat", "router", "/api/v1", ["ai"]),
    ("src.api.v1.nl_query", "router", "/api/v1", ["ai"]),
    ("src.api.v1.watchlist", "router", "/api/v1", ["watchlist"]),
    ("src.api.v1.webhook_triggers", "router", "/api/v1", ["webhooks"]),
    ("src.api.v1.presence", "router", "/api/v1", ["collaboration"]),
    ("src.api.v1.mentions", "router", "/api/v1", ["collaboration"]),
    ("src.api.v1.report_schedules", "router", "/api/v1", ["reports"]),
    ("src.api.v1.report_builder", "router", "/api/v1", ["reports"]),
    ("src.api.v1.task_board", "router", "/api/v1", ["tasks"]),
    ("src.api.v1.templates", "router", "/api/v1", ["templates"]),
    ("src.api.v1.integrations", "router", "/api/v1", ["integrations"]),
    ("src.api.v1.ticketing", "router", "/api/v1", ["ticketing"]),
    ("src.api.v1.graph_analytics", "router", "/api/v1", ["graph"]),
    ("src.api.v1.evidence.router", "router", "/api/v1", ["evidence"]),
    ("src.api.v1.investigation_diff", "router", "/api/v1", ["investigations"]),
    ("src.api.v1.saved_searches", "router", "/api/v1", ["saved-searches"]),
    ("src.api.v1.lineage", "router", "/api/v1", ["lineage"]),
    ("src.api.v1.versioning", "router", "/api/v1", ["versioning"]),
    ("src.api.v1.redaction", "router", "/api/v1", ["redaction"]),
    ("src.api.v1.report_narrative", "router", "/api/v1", ["reports"]),
    ("src.api.v1.email_ingestion", "router", "/api/v1", ["ingestion"]),
    ("src.api.v1.browser_extension", "router", "/api/v1", ["extension"]),
    ("src.api.graphql.router", "router", "/api", ["graphql"]),
    ("src.api.v1.api_versions", "router", "/api/v1", ["api-versions"]),
    ("src.api.v1.ml", "router", "/api/v1", ["ml"]),
    ("src.api.v1.bulk_actions", "router", "/api/v1", ["bulk"]),
    ("src.api.v1.campaigns", "router", "/api/v1/campaigns", ["campaigns"]),
    ("src.api.v1.annotations", "router", "/api/v1", ["annotations"]),
    ("src.api.v1.scan_profiles", "router", "/api/v1/scan-profiles", ["scan-profiles"]),
    ("src.api.v1.share_links", "router", "/api/v1", ["share-links"]),
    ("src.api.v1.activity_feed", "router", "/api/v1", ["activity"]),
    ("src.api.v1.sse", "router", "/api/v1", ["streaming"]),
    ("src.api.v1.investigation_merge", "router", "/api/v1/investigations", ["investigations"]),
    ("src.api.v1.ioc_feed", "router", "/api/v1", ["ioc-feed"]),
    ("src.api.v1.attack_surface", "router", "/api/v1", ["attack-surface"]),
    ("src.api.v1.forensic_timeline", "router", "/api/v1", ["forensic-timeline"]),
    ("src.api.v1.multi_investigation_graph", "router", "/api/v1", ["multi-graph"]),
    ("src.api.v1.tlp", "router", "/api/v1", ["tlp"]),
    ("src.api.v1.retention", "router", "/api/v1/retention", ["retention"]),
    ("src.api.v1.image_checker.router", "router", "/api/v1/image-checker", ["image-checker"]),
    ("src.api.v1.doc_metadata.router", "router", "/api/v1/doc-metadata", ["doc-metadata"]),
    ("src.api.v1.email_headers.router", "router", "/api/v1/email-headers", ["email-headers"]),
    ("src.api.v1.mac_lookup.router", "router", "/api/v1/mac-lookup", ["mac-lookup"]),
    ("src.api.v1.domain_permutation.router", "router", "/api/v1/domain-permutation", ["domain-permutation"]),
    ("src.api.v1.cloud_exposure.router", "router", "/api/v1/cloud-exposure", ["cloud-exposure"]),
    ("src.api.v1.stealer_logs.router", "router", "/api/v1/stealer-logs", ["stealer-logs"]),
    ("src.api.v1.supply_chain.router", "router", "/api/v1/supply-chain", ["supply-chain"]),
    ("src.api.v1.fediverse.router", "router", "/api/v1/fediverse", ["fediverse"]),
    ("src.api.v1.facebook_intel.router", "router", "/api/v1/facebook-intel", ["facebook-intel"]),
    ("src.api.v1.instagram_intel.router", "router", "/api/v1/instagram-intel", ["instagram-intel"]),
    ("src.api.v1.linkedin_intel.router", "router", "/api/v1/linkedin-intel", ["linkedin-intel"]),
    ("src.api.v1.github_intel.router", "router", "/api/v1/github-intel", ["github-intel"]),
    ("src.api.v1.vehicle_osint.router", "router", "/api/v1/vehicle-osint", ["vehicle-osint"]),
    ("src.api.v1.wigle.router", "router", "/api/v1/wigle", ["wigle"]),
    ("src.api.v1.tech_recon.router", "router", "/api/v1/tech-recon", ["tech-recon"]),
    ("src.api.v1.socmint.router", "router", "/api/v1/socmint", ["socmint"]),
    ("src.api.v1.credential_intel.router", "router", "/api/v1/credential-intel", ["credential-intel"]),
    ("src.api.v1.imint.router", "router", "/api/v1/imint", ["imint"]),
    # ── Pentesting platform ───────────────────────────────────────────────────
    ("src.api.v1.pentesting.router", "router", "/api/v1/pentesting", ["pentesting"]),
    ("src.api.v1.redteam.router", "router", "/api/v1/redteam", ["red-team"]),
    ("src.api.v1.engagements.router", "router", "/api/v1/engagements", ["pentest-engagements"]),
    ("src.api.v1.pentest_scans.router", "router", "/api/v1/scans", ["pentest-scans"]),
    ("src.api.v1.pentest_scans.llm_router", "router", "/api/v1/scans", ["pentest-llm"]),
    ("src.api.v1.pentest_scans.cvss_router", "router", "/api/v1", ["cvss"]),
    ("src.api.v1.pentest_findings.router", "router", "/api/v1/findings", ["pentest-findings"]),
    ("src.api.v1.pentest_findings.dedup_router", "router", "/api/v1", ["pentest-findings-dedup"]),
    ("src.api.v1.pentest_reports.router", "router", "/api/v1", ["pentest-reports"]),
    ("src.api.v1.pentest_audit.router", "router", "/api/v1/audit-log", ["pentest-audit"]),
    ("src.api.v1.hitl.router", "router", "/api/v1/hitl", ["pentest-hitl"]),
    ("src.api.v1.attack_chains.router", "router", "/api/v1/scans", ["pentest-attack-chains"]),
    ("src.api.v1.rag.router", "router", "/api/v1", ["rag"]),
    ("src.api.v1.ai_planner.router", "router", "/api/v1", ["ai-planner"]),
    ("src.api.v1.test_catalog.router", "router", "/api/v1", ["test-catalog"]),
    ("src.api.v1.bas.router", "router", "/api/v1/bas", ["bas"]),
    ("src.api.v1.sarif.router", "router", "/api/v1", ["pentest-export"]),
    ("src.api.v1.finding_library.router", "router", "/api/v1/finding-library", ["finding-library"]),
    ("src.api.v1.retest.router", "router", "/api/v1", ["retest"]),
    ("src.api.v1.notifications.router", "router", "/api/v1/notifications", ["notifications"]),
    ("src.api.v1.api_keys.router", "router", "/api/v1/api-keys", ["api-keys"]),
    ("src.api.v1.pentest_integrations.jira_router", "router", "/api/v1/integrations", ["integrations"]),
    ("src.api.v1.pentest_integrations.siem_router", "router", "/api/v1/integrations", ["integrations-siem"]),
    ("src.api.v1.team.router", "router", "/api/v1", ["team"]),
    ("src.api.v1.assets.router", "router", "/api/v1", ["assets"]),
    ("src.api.v1.phishing.router", "router", "/api/v1", ["phishing"]),
    ("src.api.v1.peer_review.router", "router", "/api/v1", ["peer-review"]),
    ("src.api.v1.agent.router", "router", "/api/v1", ["agent"]),
    ("src.api.v1.hub.router", "router", "/api/v1", ["hub"]),
    ("src.api.v1.hub_tasks.router", "router", "/api/v1", ["hub-tasks"]),
    ("src.api.v1.knowledge.router", "router", "/api/v1", ["knowledge"]),
    ("src.api.v1.threat_actors", "router", "/api/v1", ["threat-actors"]),
    # ── Web Attack Tools (Batch 1) ────────────────────────────────────────────
    ("src.api.v1.web_attack_tools.router", "router", "/api/v1/web-attack-tools", ["web-attack-tools"]),
    # ── Auth & Vuln Tools (Batch 2) ───────────────────────────────────────────
    ("src.api.v1.auth_vuln_tools.router", "router", "/api/v1/auth-vuln-tools", ["auth-vuln-tools"]),
    # ── AD & Infrastructure Tools (Batch 3) ──────────────────────────────────
    ("src.api.v1.ad_infra_tools.router", "router", "/api/v1/ad-infra-tools", ["ad-infra-tools"]),
    # ── Advanced Scanners (Batch 4 — Improvement 1) ───────────────────────────
    ("src.api.v1.advanced_scanners.router", "router", "", ["advanced-scanners"]),
    # ── AD Credential Attacks (Batch 4 — Improvement 4) ──────────────────────
    ("src.api.v1.ad_cred_attacks.router", "router", "", ["ad-cred-attacks"]),
    # ── Web Exploit Tools (New Batch Features 1–7) ────────────────────────────
    ("src.api.v1.web_exploit.router", "router", "", ["web-exploit"]),
    # ── Post-Exploit Tools (New Batch Features 8–10) ─────────────────────────
    ("src.api.v1.post_exploit.router", "router", "", ["post-exploit"]),
    # ── Exploit Tools (Features 11-14: OAuth, Atomic, XXE/SSRF, AdaptixC2) ──
    ("src.api.v1.exploit_tools.router", "router", "", ["exploit-tools"]),
    # ── AD Attack Tools (Features 15-19: LDAP, Ligolo, ACL, PtH, ADCS) ──────
    ("src.api.v1.ad_attack.router", "router", "", ["ad-attack"]),
    # ── Batch 3: Cloud Pentest (Features 21-25) ───────────────────────────────
    ("src.api.v1.cloud_pentest.router", "router", "", ["cloud-pentest"]),
    # ── Batch 3: Wireless Pentest (Features 26-28) ────────────────────────────
    ("src.api.v1.wireless_pentest.router", "router", "", ["wireless-pentest"]),
    # ── Batch 3: Reporting Tools (Features 29-30) ─────────────────────────────
    ("src.api.v1.reporting_tools.router", "router", "", ["reporting-tools"]),
    # ── OSINT scanners & analysis ─────────────────────────────────────────────
    ("src.api.v1.scanner_health", "router", "/api/v1", ["scanners"]),
    ("src.api.v1.dark_web", "router", "", ["dark-web"]),
    ("src.api.v1.passive_dns", "router", "", ["passive-dns"]),
    ("src.api.v1.footprint", "router", "", ["footprint"]),
    ("src.api.v1.cert_transparency", "router", "", ["cert-transparency"]),
    ("src.api.v1.crypto_trace", "router", "", ["crypto-trace"]),
    ("src.api.v1.corporate_intel", "router", "", ["corporate-intel"]),
    ("src.api.v1.deep_research", "router", "", ["deep-research"]),
    ("src.api.v1.phone_intel", "router", "", ["phone-intel"]),
    ("src.api.v1.social_graph", "router", "", ["social-graph"]),
    ("src.api.v1.brand_protection", "router", "", ["brand-protection"]),
    ("src.api.v1.correlation", "router", "", ["correlation"]),
    ("src.api.v1.evidence_locker", "router", "", ["evidence-locker"]),
    ("src.api.v1.vuln_management", "router", "", ["vuln-management"]),
    ("src.api.v1.phishing_campaigns", "router", "", ["phishing-campaigns"]),
    ("src.api.v1.exploit_chain", "router", "", ["exploit-chain"]),
    ("src.api.v1.c2_integration", "router", "", ["c2-integration"]),
    ("src.api.v1.network_topology", "router", "", ["network-topology"]),
    ("src.api.v1.wireless_auditor", "router", "", ["wireless-auditor"]),
    ("src.api.v1.domain_intel", "router", "", ["domain-intel"]),
    ("src.api.v1.methodology", "router", "", ["methodology"]),
    ("src.api.v1.collaboration", "router", "", ["collaboration"]),
    ("src.api.v1.retest_engine", "router", "", ["retest-engine"]),
    ("src.api.v1.client_portal", "router", "", ["client-portal"]),
    ("src.api.v1.secure_notes", "router", "", ["secure-notes"]),
    ("src.api.v1.time_tracking", "router", "", ["time-tracking"]),
    ("src.api.v1.sla", "router", "", ["sla"]),
    ("src.api.v1.ai_debrief", "router", "", ["ai-debrief"]),
    ("src.api.v1.threat_feed", "router", "", ["threat-feed"]),
    ("src.api.v1.canary", "router", "", ["canary"]),
    ("src.api.v1.custom_scanner", "router", "", ["custom-scanner"]),
    ("src.api.v1.knowledge_base", "router", "", ["knowledge-base"]),
    ("src.api.v1.client_handoff", "router", "", ["client-handoff"]),
    ("src.api.v1.scenarios.marketplace_router", "router", "/api/v1", ["scenario-marketplace"]),
    ("src.api.v1.workflows.n8n_router", "router", "/api/v1", ["n8n-workflows"]),
    ("src.api.v1.tools.custom_tools_router", "router", "/api/v1", ["custom-tools"]),
    ("src.api.v1.rbac.router", "router", "/api/v1", ["rbac"]),
    ("src.api.v1.gdpr.router", "router", "/api/v1", ["gdpr-compliance"]),
    # OSINT ↔ Pentest integration bridge
    ("src.api.v1.investigations.pentest_integration", "investigations_router", "/api/v1/investigations", ["osint-pentest-integration"]),
    ("src.api.v1.investigations.pentest_integration", "scans_router", "/api/v1/scans", ["osint-pentest-integration"]),
    # ── WorldMonitor ──────────────────────────────────────────────────────────
    ("src.api.v1.worldmonitor.router", "router", "/worldmonitor/api", ["world-monitor"]),

    # ── New features (batch 2) ────────────────────────────────────────────────
    ("src.api.v1.investigation_risk_score", "router", "/api/v1", ["risk-score"]),
    ("src.api.v1.stix_export", "router", "/api/v1", ["stix-export"]),
    ("src.api.v1.investigation_acl", "router", "/api/v1", ["investigation-acl"]),
    ("src.api.v1.scanner_quota", "router", "/api/v1", ["scanner-quota"]),
    ("src.api.v1.scheduled_rescan", "router", "/api/v1", ["scheduled-rescan"]),
    ("src.api.v1.pivot_recommendations", "router", "/api/v1", ["pivot-recommendations"]),
    ("src.api.v1.attack_flow", "router", "/api/v1", ["attack-flow"]),

    # ── New OSINT tools (batch 3) ────────────────────────────────────────────
    ("src.api.v1.malware_hash.router", "router", "/api/v1/malware-hash", ["malware-hash"]),
    ("src.api.v1.asn_intel.router", "router", "/api/v1/asn-intel", ["asn-intel"]),
    ("src.api.v1.email_pivot.router", "router", "/api/v1/email-pivot", ["email-pivot"]),
    ("src.api.v1.http_fingerprint.router", "router", "/api/v1/http-fingerprint", ["http-fingerprint"]),
    ("src.api.v1.exploit_intel.router", "router", "/api/v1/exploit-intel", ["exploit-intel"]),
    ("src.api.v1.subdomain_takeover.router", "router", "/api/v1/subdomain-takeover", ["subdomain-takeover"]),
    ("src.api.v1.paste_monitor.router", "router", "/api/v1/paste-monitor", ["paste-monitor"]),
    ("src.api.v1.ransomware_tracker.router", "router", "/api/v1/ransomware-tracker", ["ransomware-tracker"]),
    ("src.api.v1.username_scanner.router", "router", "/api/v1/username-scanner", ["username-scanner"]),
]


def _include_all_routers(application: FastAPI) -> None:
    """Register all routers from the registry.

    In production (debug=False) any router that fails to import raises immediately
    so a misconfigured deployment is caught at startup rather than silently serving
    incomplete endpoints.  In debug mode, the error is logged and skipped so
    developers can work with partially-installed optional modules.
    """
    settings = get_settings()
    for module_path, attr_name, prefix, tags in _ROUTER_REGISTRY:
        try:
            module = importlib.import_module(module_path)
            router = getattr(module, attr_name)
            application.include_router(router, prefix=prefix, tags=tags)
        except (ImportError, AttributeError) as exc:
            if settings.debug:
                log.warning("router_load_failed", module=module_path, attr=attr_name, error=str(exc))
            else:
                raise RuntimeError(
                    f"Failed to load router '{module_path}.{attr_name}': {exc}. "
                    "Fix the import error or set DEBUG=true to skip missing routers."
                ) from exc


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Initialize structured logging with structlog."""
    import structlog
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


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    await log.ainfo("Starting OSINT platform backend")

    settings = get_settings()
    try:
        import redis.asyncio as aioredis
        app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await app.state.redis.ping()
        await log.ainfo("Redis connection established")
    except Exception as exc:
        log.warning("Redis not available, rate limiting disabled", error=str(exc))
        app.state.redis = None

    try:
        from src.adapters.search.elasticsearch_store import ElasticsearchStore
        es = ElasticsearchStore()
        await es.ensure_indices()
        app.state.elasticsearch = es
        await log.ainfo("Elasticsearch indices ensured")
    except Exception as exc:
        log.warning("Elasticsearch not available", error=str(exc))
        app.state.elasticsearch = None

    from src.adapters.db.audit_models import AuditLogModel  # noqa: F401

    # Auto-create MinIO bucket on startup so workers don't fail on first upload
    try:
        import asyncio
        from minio import Minio
        _minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        loop = asyncio.get_event_loop()
        found = await loop.run_in_executor(None, _minio.bucket_exists, settings.minio_bucket)
        if not found:
            await loop.run_in_executor(None, _minio.make_bucket, settings.minio_bucket)
            await log.ainfo("MinIO bucket created", bucket=settings.minio_bucket)
        else:
            await log.ainfo("MinIO bucket already exists", bucket=settings.minio_bucket)
    except Exception as exc:
        log.warning("MinIO not available", error=str(exc))

    # WorldMonitor background scheduler (RSS aggregation every 5 min)
    try:
        from src.worldmonitor.scheduler import scheduler as wm_scheduler
        if app.state.redis is not None:
            await wm_scheduler.start(app.state.redis)
            await log.ainfo("WorldMonitor scheduler started")
    except Exception as exc:
        log.warning("worldmonitor_scheduler_unavailable", error=str(exc))

    if not settings.debug and settings.proxy_mode == "direct":
        log.warning(
            "opsec_warning",
            message=(
                "proxy_mode is 'direct': all scanner traffic originates from this server's real IP. "
                "Set PROXY_MODE=tor or PROXY_MODE=socks5 in production to protect investigator identity."
            ),
        )

    yield

    await log.ainfo("Shutting down OSINT platform backend")
    try:
        from src.worldmonitor.scheduler import scheduler as wm_scheduler
        await wm_scheduler.stop()
    except Exception:
        pass
    if getattr(app.state, "elasticsearch", None) is not None:
        await app.state.elasticsearch.close()
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.close()
    await engine.dispose()
    await log.ainfo("Database pool disposed")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

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

    from src.adapters.telemetry import setup_telemetry
    setup_telemetry(application)

    # Middleware (outermost first)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestLoggingMiddleware)

    try:
        from src.api.middleware.locale import LocaleMiddleware
        application.add_middleware(LocaleMiddleware)
    except ImportError:
        pass

    # Global exception handlers
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "details": None,
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        def _sanitize(obj: object) -> object:
            if isinstance(obj, bytes):
                return obj.decode("utf-8", errors="replace")
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize(i) for i in obj]
            return obj

        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "code": "VALIDATION_ERROR",
                "details": _sanitize(exc.errors()),
            },
        )

    _include_all_routers(application)

    return application


app = create_app()
