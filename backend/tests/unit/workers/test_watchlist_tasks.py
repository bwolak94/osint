"""Tests for watchlist Celery tasks."""

import sys
import pytest
from unittest.mock import MagicMock, patch


class TestWatchlistTasks:
    def test_process_watchlist_returns_counts(self):
        # Mock celery since it's not installed locally
        mock_celery = MagicMock()
        mock_celery.task = lambda *a, **kw: lambda f: f

        with patch.dict(sys.modules, {
            "celery": mock_celery,
            "src.workers.celery_app": MagicMock(celery_app=mock_celery),
        }):
            # Force reimport with mocked celery
            if "src.workers.tasks.watchlist_tasks" in sys.modules:
                del sys.modules["src.workers.tasks.watchlist_tasks"]

            from src.workers.tasks.watchlist_tasks import process_watchlist

            result = process_watchlist()
            assert "processed" in result
            assert "changed" in result
            assert result["processed"] == 0
