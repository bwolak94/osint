"""Tests for task board endpoints."""

import pytest
from unittest.mock import MagicMock


class TestTaskBoardEndpoints:
    async def test_list_tasks_empty(self):
        from src.api.v1.task_board import list_tasks
        mock_user = MagicMock()
        result = await list_tasks(investigation_id="inv-1", current_user=mock_user)
        assert result.tasks == []
        assert result.by_status["todo"] == 0

    async def test_create_task(self):
        from src.api.v1.task_board import create_task, TaskCreate
        mock_user = MagicMock()
        mock_user.id = "user-1"
        body = TaskCreate(
            investigation_id="inv-1",
            title="Review scan results",
            priority="high",
            labels=["review"],
        )
        result = await create_task(investigation_id="inv-1", body=body, current_user=mock_user)
        assert result.title == "Review scan results"
        assert result.priority == "high"
        assert result.status == "todo"

    async def test_update_task(self):
        from src.api.v1.task_board import update_task, TaskUpdate
        mock_user = MagicMock()
        body = TaskUpdate(status="done")
        result = await update_task(investigation_id="inv-1", task_id="task-1", body=body, current_user=mock_user)
        assert result["status"] == "updated"

    async def test_delete_task(self):
        from src.api.v1.task_board import delete_task
        mock_user = MagicMock()
        result = await delete_task(investigation_id="inv-1", task_id="task-1", current_user=mock_user)
        assert result["status"] == "deleted"
