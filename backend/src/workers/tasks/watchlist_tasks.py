"""Celery tasks for watch list processing."""

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="src.workers.tasks.watchlist_tasks.process_watchlist")
def process_watchlist():
    """Periodically process active watch list items.

    For each active item whose schedule is due:
    1. Run the configured scanners
    2. Hash the results
    3. Compare with last_result_hash
    4. If changed, notify via configured channels
    """
    log.info("Processing watch list items")
    # Placeholder: In full implementation, query active items from DB,
    # check if their cron schedule is due, run scans, compare results
    return {"processed": 0, "changed": 0}
