"""Celery application configuration."""

from celery import Celery

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "osint_workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in the workers.tasks package
celery_app.autodiscover_tasks(["src.workers.tasks"])
