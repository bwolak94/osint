"""Celery application configuration with bulkhead queue pattern."""

from celery import Celery

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
        "src.workers.tasks.scanner_tasks.holehe_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.maigret_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.vat_scan_task": {"queue": "light"},
        "src.workers.tasks.scanner_tasks.playwright_scan_task": {"queue": "heavy"},
        "src.workers.tasks.graph_tasks.*": {"queue": "graph"},
        "src.workers.tasks.investigation_tasks.*": {"queue": "light"},
    },

    # Rate limiting per task
    task_annotations={
        "src.workers.tasks.scanner_tasks.holehe_scan_task": {"rate_limit": "30/m"},
        "src.workers.tasks.scanner_tasks.maigret_scan_task": {"rate_limit": "20/m"},
        "src.workers.tasks.scanner_tasks.playwright_scan_task": {"rate_limit": "10/m"},
    },

    # Default queue
    task_default_queue="light",

    # Result expiry (24 hours)
    result_expires=86400,
)

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "src.workers.tasks",
])
