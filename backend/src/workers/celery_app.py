"""Celery application configuration with bulkhead queue pattern."""

from celery import Celery
from celery.schedules import crontab

from src.config import get_settings

settings = get_settings()

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

    # Retry defaults
    task_max_retries=3,
    task_default_retry_delay=60,

    # Bulkhead pattern: route tasks to separate queues
    task_routes={
        # RAG ingestion tasks (light — network-bound, not CPU-intensive)
        "rag.ingest_all_sources": {"queue": "light"},
        # PentAI pentest tasks
        "src.workers.pentest_orchestrator.orchestrate_scan": {"queue": "pentest_heavy"},
        "src.workers.pentest_orchestrator.run_tool_module": {"queue": "pentest_heavy"},
        "src.workers.pentest_orchestrator.generate_pentest_report": {"queue": "pentest_light"},
        "src.workers.pentest_orchestrator.check_sla_breaches": {"queue": "pentest_light"},
        "src.workers.retest_tasks.retest_finding": {"queue": "pentest_heavy"},
        "src.workers.notification_tasks.notify_finding_created": {"queue": "pentest_light"},
        "src.workers.notification_tasks.notify_scan_complete": {"queue": "pentest_light"},
        "src.workers.notification_tasks.dispatch_webhook": {"queue": "pentest_light"},
        "src.workers.tasks.scanner_tasks.holehe_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.maigret_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.vat_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.playwright_scan_task": {"queue": "heavy"},
        "src.workers.tasks.graph_tasks.*": {"queue": "graph"},
        "src.workers.tasks.investigation_tasks.*": {"queue": "light"},
        "src.workers.tasks.scheduled_scan_tasks.*": {"queue": "light"},
        "src.workers.tasks.retention_tasks.*": {"queue": "light"},
        "src.workers.tasks.ioc_enrichment_tasks.*": {"queue": "light"},
        "src.workers.tasks.alert_tasks.*": {"queue": "light"},
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
            "schedule": 300.0,  # every 5 minutes
        },
        "run-scheduled-rescans": {
            "task": "src.workers.tasks.scheduled_scan_tasks.process_scheduled_rescans",
            "schedule": 600.0,  # every 10 minutes
        },
        "enforce-retention-policies": {
            "task": "src.workers.tasks.retention_tasks.enforce_retention_policies",
            "schedule": 3600.0,  # every hour
        },
        "pentest-check-sla-breaches": {
            "task": "src.workers.pentest_orchestrator.check_sla_breaches",
            "schedule": 3600.0,  # every hour
        },
        "pentest-verify-audit-chains": {
            "task": "src.workers.pentest_orchestrator.verify_audit_chains",
            "schedule": 86400.0,  # daily
        },
        "rag-nightly-ingest": {
            "task": "rag.ingest_all_sources",
            "schedule": crontab(hour=2, minute=0),  # 02:00 UTC daily
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
