"""Backwards-compatible import — real tasks are in scanner_tasks.py."""
# Import from scanner_tasks for backwards compatibility
from src.workers.tasks.scanner_tasks import *  # noqa: F401, F403
