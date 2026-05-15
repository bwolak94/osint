"""Celery application configuration with bulkhead queue pattern."""

from celery import Celery
from celery.schedules import crontab

from src.config import get_settings

settings = get_settings()

# ── Beat schedule intervals ───────────────────────────────────────────────────
# Named constants make the schedule table readable and allow env-var overrides.
_WATCHLIST_INTERVAL_S: float = 300.0        # 5 min
_SCHEDULED_RESCAN_INTERVAL_S: float = 600.0  # 10 min
_RETENTION_INTERVAL_S: float = 3600.0        # 1 h
_SLA_CHECK_INTERVAL_S: float = 3600.0        # 1 h
_HITL_EXPIRE_INTERVAL_S: float = 300.0       # 5 min
_NEWS_SCRAPE_INTERVAL_S: float = 1800.0      # 30 min

celery_app = Celery("osint_workers", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Reliability
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Retry defaults — 10 s is fast enough for transient errors without making
    # investigations appear stuck for a full minute before the first retry.
    task_max_retries=3,
    task_default_retry_delay=10,

    # Bulkhead pattern: route tasks to separate queues
    task_routes={
        # RAG ingestion tasks (light — network-bound, not CPU-intensive)
        "rag.ingest_all_sources": {"queue": "light"},
        # PentAI pentest tasks
        "src.workers.pentest_orchestrator.orchestrate_scan": {"queue": "pentest_heavy"},
        "src.workers.pentest_orchestrator.run_tool_module": {"queue": "pentest_heavy"},
        "src.workers.pentest_orchestrator.generate_pentest_report": {"queue": "pentest_light"},
        "src.workers.pentest_orchestrator.check_sla_breaches": {"queue": "pentest_light"},
        "src.workers.pentest_orchestrator.expire_stale_hitl_requests": {"queue": "pentest_light"},
        "src.workers.retest_tasks.retest_finding": {"queue": "pentest_heavy"},
        "src.workers.notification_tasks.notify_finding_created": {"queue": "pentest_light"},
        "src.workers.notification_tasks.notify_scan_complete": {"queue": "pentest_light"},
        "src.workers.notification_tasks.dispatch_webhook": {"queue": "pentest_light"},
        "src.workers.tasks.scanner_tasks.holehe_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.maigret_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.vat_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.playwright_scan_task": {"queue": "heavy"},
        "facebook_intel.scrape": {"queue": "heavy"},
        "instagram_intel.scrape": {"queue": "heavy"},
        "linkedin_intel.scrape": {"queue": "heavy"},
        "github_intel.fetch": {"queue": "light"},
        "vehicle_osint.fetch": {"queue": "light"},
        "hub.run_agent": {"queue": "light"},
        "hub.resume_agent": {"queue": "light"},
        "news.scrape_all": {"queue": "light"},
        # Note: Celery routes by exact task name — glob patterns are not supported.
        # Each task name must be listed explicitly.
        "src.workers.tasks.graph_tasks.resolve_entities_task": {"queue": "graph"},
        "src.workers.tasks.graph_tasks.build_graph_task": {"queue": "graph"},
        "src.workers.tasks.graph_tasks.community_detection_tasks.detect_communities": {"queue": "graph"},
        "src.workers.tasks.graph_tasks.community_detection_tasks.propagate_confidence": {"queue": "graph"},
        "src.workers.tasks.investigation_tasks.run_investigation_task": {"queue": "light"},
        "src.workers.tasks.investigation_tasks.run_osint_investigation": {"queue": "light"},
        "src.workers.tasks.investigation_tasks._complete_investigation_task": {"queue": "light"},
        "src.workers.tasks.scheduled_scan_tasks.process_scheduled_rescans": {"queue": "light"},
        "src.workers.tasks.retention_tasks.enforce_retention_policies": {"queue": "light"},
        "src.workers.tasks.retention_tasks.cold_archive_investigation": {"queue": "light"},
        "src.workers.tasks.ioc_enrichment_tasks.enrich_ioc": {"queue": "light"},
        "src.workers.tasks.alert_tasks.evaluate_trigger_rules": {"queue": "light"},
        "osint.enrich_from_pentest": {"queue": "light"},
        "src.workers.tasks.community_detection_tasks.detect_communities": {"queue": "graph"},
        "src.workers.tasks.community_detection_tasks.propagate_confidence": {"queue": "graph"},
        "src.workers.tasks.community_detection_tasks.score_attribution": {"queue": "light"},
    },

    # Rate limiting per task
    task_annotations={
        "src.workers.tasks.scanner_tasks.holehe_scan_task": {"rate_limit": "30/m"},
        "src.workers.tasks.scanner_tasks.maigret_scan_task": {"rate_limit": "20/m"},
        "src.workers.tasks.scanner_tasks.playwright_scan_task": {"rate_limit": "10/m"},
        "src.workers.tasks.ioc_enrichment_tasks.enrich_ioc": {"rate_limit": "60/m"},
        "src.workers.tasks.alert_tasks.evaluate_trigger_rules": {"rate_limit": "120/m"},
    },

    # Default queue
    task_default_queue="light",

    # Result expiry (24 hours)
    result_expires=86400,

    # Celery beat schedule for periodic tasks
    beat_schedule={
        "process-watchlist-items": {
            "task": "src.workers.tasks.watchlist_tasks.process_watchlist",
            "schedule": _WATCHLIST_INTERVAL_S,
        },
        "run-scheduled-rescans": {
            "task": "src.workers.tasks.scheduled_scan_tasks.process_scheduled_rescans",
            "schedule": _SCHEDULED_RESCAN_INTERVAL_S,
        },
        "enforce-retention-policies": {
            "task": "src.workers.tasks.retention_tasks.enforce_retention_policies",
            "schedule": _RETENTION_INTERVAL_S,
        },
        "pentest-check-sla-breaches": {
            "task": "src.workers.pentest_orchestrator.check_sla_breaches",
            "schedule": _SLA_CHECK_INTERVAL_S,
        },
        "pentest-verify-audit-chains": {
            "task": "src.workers.pentest_orchestrator.verify_audit_chains",
            "schedule": crontab(hour=1, minute=0),  # 01:00 UTC daily
        },
        "pentest-expire-stale-hitl": {
            "task": "src.workers.pentest_orchestrator.expire_stale_hitl_requests",
            "schedule": _HITL_EXPIRE_INTERVAL_S,
        },
        "rag-nightly-ingest": {
            "task": "rag.ingest_all_sources",
            "schedule": crontab(hour=2, minute=0),  # 02:00 UTC daily
        },
        "news-scrape-feeds": {
            "task": "news.scrape_all",
            "schedule": _NEWS_SCRAPE_INTERVAL_S,
        },
        "purge-celery-results": {
            "task": "src.workers.scheduled_tasks.purge_celery_results",
            "schedule": crontab(hour=3, minute=0),  # 03:00 UTC daily
        },
        "purge-expired-refresh-tokens": {
            "task": "src.workers.tasks.cleanup_tasks.purge_expired_refresh_tokens",
            "schedule": crontab(hour=4, minute=0),  # 04:00 UTC daily
        },
        "reset-monthly-scanner-quotas": {
            "task": "src.workers.scheduled_tasks.reset_monthly_quotas",
            "schedule": crontab(day_of_month=1, hour=0, minute=5),  # 1st of month 00:05 UTC
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "src.workers.tasks",
    "src.workers",
])

# Explicitly import pentest orchestrator so tasks are registered
import src.workers.pentest_orchestrator  # noqa: E402, F401
import src.workers.retest_tasks  # noqa: E402, F401
import src.workers.notification_tasks  # noqa: E402, F401

# Explicitly import RAG ingestion so its tasks are registered
import src.workers.rag_ingestion  # noqa: E402, F401

# Register signal handlers for structured logging and failure alerting
import src.workers.celery_signals  # noqa: E402, F401

# Register scheduled/maintenance tasks
import src.workers.scheduled_tasks  # noqa: E402, F401

# Explicitly import OSINT enrichment consumer so its tasks are registered
import src.workers.osint_enrichment_consumer  # noqa: E402, F401

# Explicitly import investigation / scanner tasks so they are registered
# ---------------------------------------------------------------------------
# Correlation ID propagation (#24)
# Injects the HTTP request's X-Correlation-ID into structlog context inside
# each worker so distributed traces span both the API and the worker tier.
# ---------------------------------------------------------------------------
from celery.signals import task_prerun  # noqa: E402

@task_prerun.connect
def _inject_correlation_id(task_id: str, task: object, **kwargs: object) -> None:
    """Copy correlation ID from Celery task headers into structlog context."""
    try:
        import structlog
        headers: dict = getattr(getattr(task, "request", None), "headers", None) or {}
        correlation_id = headers.get("x-correlation-id") or task_id
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    except Exception:
        pass  # Never break task execution due to observability failure

import src.workers.tasks.investigation_tasks  # noqa: E402, F401
import src.workers.tasks.scanner_tasks  # noqa: E402, F401
import src.workers.tasks.graph_tasks  # noqa: E402, F401

# Register cleanup tasks (expired refresh token purge, etc.)
import src.workers.tasks.cleanup_tasks  # noqa: E402, F401

# Explicitly import Hub AI agent tasks so they are registered
import src.workers.tasks.hub_tasks  # noqa: E402, F401

# Explicitly import news scraper task so it is registered with Celery beat
import src.workers.tasks.news_scraper_task  # noqa: E402, F401

# Register Facebook Intel heavy task
import src.workers.tasks.facebook_intel_task  # noqa: E402, F401

# Register Instagram Intel heavy task
import src.workers.tasks.instagram_intel_task  # noqa: E402, F401

# Register LinkedIn Intel heavy task
import src.workers.tasks.linkedin_intel_task  # noqa: E402, F401

# Register GitHub Intel light task
import src.workers.tasks.github_intel_task  # noqa: E402, F401

# Register Vehicle OSINT light task
import src.workers.tasks.vehicle_osint_task  # noqa: E402, F401

# celery_signals already imported above (line ~155) — do not import again here
# as signal handlers would be registered twice.
