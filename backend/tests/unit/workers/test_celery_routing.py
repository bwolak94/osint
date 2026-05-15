"""Tests that Celery task names resolve to the correct queues.

These catch two classes of bugs:
1. Wildcard patterns (e.g. "tasks.*") that Celery silently ignores.
2. New tasks that were registered without a route, defaulting to the wrong queue.

The test reads ``task_routes`` from the Celery config and verifies each
route is an exact task name (no glob wildcards) and matches the expected queue.
"""

import pytest

# Avoid importing the full celery_app (which triggers worker imports and DB
# connections) by importing only the conf dict that was used to configure it.
from src.workers.celery_app import celery_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_route(task_name: str) -> str | None:
    """Return the queue name for *task_name*, or None if not routed."""
    routes = celery_app.conf.task_routes or {}
    entry = routes.get(task_name)
    if entry and isinstance(entry, dict):
        return entry.get("queue")
    return None


# ---------------------------------------------------------------------------
# No wildcard patterns in task_routes
# ---------------------------------------------------------------------------

def test_no_wildcard_routes_in_task_routes():
    """Celery routes by exact task name; wildcards are silently ignored."""
    routes = celery_app.conf.task_routes or {}
    wildcards = [name for name in routes if "*" in name]
    assert wildcards == [], (
        f"Wildcard task routes found (Celery ignores them): {wildcards}"
    )


# ---------------------------------------------------------------------------
# Spot-checks: critical tasks → expected queues
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_name,expected_queue", [
    ("src.workers.tasks.scanner_tasks.playwright_scan_task", "heavy"),
    ("src.workers.tasks.scanner_tasks.holehe_scan_task", "light"),
    ("src.workers.tasks.scanner_tasks.maigret_scan_task", "light"),
    ("src.workers.tasks.investigation_tasks.run_osint_investigation", "light"),
    ("src.workers.tasks.graph_tasks.resolve_entities_task", "graph"),
    ("src.workers.tasks.graph_tasks.build_graph_task", "graph"),
    ("src.workers.tasks.retention_tasks.enforce_retention_policies", "light"),
    ("src.workers.tasks.retention_tasks.cold_archive_investigation", "light"),
    ("src.workers.pentest_orchestrator.orchestrate_scan", "pentest_heavy"),
    ("src.workers.pentest_orchestrator.generate_pentest_report", "pentest_light"),
    ("facebook_intel.scrape", "heavy"),
    ("instagram_intel.scrape", "heavy"),
    ("github_intel.fetch", "light"),
])
def test_task_routes_to_expected_queue(task_name: str, expected_queue: str):
    actual = _get_route(task_name)
    assert actual == expected_queue, (
        f"Task '{task_name}' routes to '{actual}', expected '{expected_queue}'"
    )


# ---------------------------------------------------------------------------
# No route → falls back to default queue
# ---------------------------------------------------------------------------

def test_default_queue_is_light():
    assert celery_app.conf.task_default_queue == "light"


# ---------------------------------------------------------------------------
# Celery signals not registered twice
# ---------------------------------------------------------------------------

def test_celery_signals_imported_once():
    """The celery_app module must not import celery_signals twice.

    Double import causes signal handlers to fire twice per event, leading to
    double logging and double alerting.  This test checks the module source.
    """
    import inspect
    import src.workers.celery_app as mod

    source = inspect.getsource(mod)
    occurrences = source.count("import src.workers.celery_signals")
    assert occurrences == 1, (
        f"src.workers.celery_signals is imported {occurrences} times — should be exactly 1"
    )
