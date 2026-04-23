"""Tests for the Hub productivity tasks API router.

Uses httpx AsyncClient with mocked dependencies — no real DB or auth.
"""

from __future__ import annotations

import sys
import types
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Stub heavy optional dependencies before any src import ─────────────────

def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    mod = MagicMock()
    mod.__name__ = name
    mod.__package__ = name.rsplit(".", 1)[0] if "." in name else name
    mod.__path__ = []
    mod.__spec__ = None
    sys.modules[name] = mod
    return mod


for _pkg in [
    "jose", "jose.jwt", "pyotp", "asyncpg", "redis", "redis.asyncio",
    "bcrypt", "neo4j", "qrcode", "holehe", "holehe.core",
    "celery", "openai", "anthropic",
]:
    _ensure_module(_pkg)

_db_mod = types.ModuleType("src.adapters.db.database")
_db_mod.engine = MagicMock()  # type: ignore[attr-defined]
_db_mod.async_session_factory = MagicMock()  # type: ignore[attr-defined]
sys.modules["src.adapters.db.database"] = _db_mod


_FAKE_USER_ID = uuid.uuid4()
_FAKE_TASK_ID = uuid.uuid4()
_NOW = datetime.now(timezone.utc)


def _make_task_dict(**kwargs: Any) -> dict[str, Any]:
    base = {
        "id": _FAKE_TASK_ID,
        "user_id": _FAKE_USER_ID,
        "title": "Test Task",
        "description": "A test task",
        "priority": 3,
        "status": "todo",
        "due_at": None,
        "source": "user",
        "source_ref_id": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(kwargs)
    return base


def _make_history_dict(**kwargs: Any) -> dict[str, Any]:
    base = {
        "id": uuid.uuid4(),
        "task_id": _FAKE_TASK_ID,
        "old_status": None,
        "new_status": "todo",
        "changed_by": "user",
        "changed_at": _NOW,
    }
    base.update(kwargs)
    return base


def _make_mock_task(data: dict[str, Any] | None = None) -> MagicMock:
    d = data or _make_task_dict()
    mock = MagicMock()
    for key, value in d.items():
        setattr(mock, key, value)
    return mock


def _make_mock_history(data: dict[str, Any] | None = None) -> MagicMock:
    d = data or _make_history_dict()
    mock = MagicMock()
    for key, value in d.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture
def mock_user() -> MagicMock:
    user = MagicMock()
    user.id = _FAKE_USER_ID
    user.is_active = True
    return user


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    task = _make_mock_task()
    history = _make_mock_history()

    repo.list_tasks = AsyncMock(return_value=[task])
    repo.get_task = AsyncMock(return_value=task)
    repo.create_task = AsyncMock(return_value=task)
    repo.update_task = AsyncMock(return_value=task)
    repo.cancel_task = AsyncMock(return_value=True)
    repo.get_history = AsyncMock(return_value=[history])
    repo.add_dependency = AsyncMock(return_value=True)
    return repo


class TestHubTasksRouterList:
    async def test_list_tasks_returns_200(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import list_tasks
        from src.api.v1.hub_tasks.schemas import TaskListResponse

        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await list_tasks(
                status_filter=None,
                priority=None,
                skip=0,
                limit=50,
                current_user=mock_user,
                db=AsyncMock(),
            )

        assert isinstance(result, TaskListResponse)
        assert result.total == 1
        assert result.skip == 0
        assert result.limit == 50

    async def test_list_tasks_with_status_filter(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import list_tasks

        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            await list_tasks(
                status_filter="todo",
                priority=None,
                skip=0,
                limit=50,
                current_user=mock_user,
                db=AsyncMock(),
            )

        mock_repo.list_tasks.assert_awaited_once()
        call_kwargs = mock_repo.list_tasks.call_args[1]
        assert call_kwargs["status"] == "todo"

    async def test_list_tasks_pagination(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import list_tasks

        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await list_tasks(
                status_filter=None,
                priority=None,
                skip=10,
                limit=5,
                current_user=mock_user,
                db=AsyncMock(),
            )

        assert result.skip == 10
        assert result.limit == 5


class TestHubTasksRouterCreate:
    async def test_create_task_returns_task_response(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import create_task
        from src.api.v1.hub_tasks.schemas import TaskCreate, TaskResponse

        body = TaskCreate(title="New Task", priority=2)
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await create_task(body=body, current_user=mock_user, db=AsyncMock())

        assert isinstance(result, TaskResponse)
        mock_repo.create_task.assert_awaited_once()


class TestHubTasksRouterGetDetail:
    async def test_get_existing_task(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import get_task
        from src.api.v1.hub_tasks.schemas import TaskResponse

        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await get_task(
                task_id=_FAKE_TASK_ID,
                current_user=mock_user,
                db=AsyncMock(),
            )

        assert isinstance(result, TaskResponse)

    async def test_get_nonexistent_task_raises_404(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from fastapi import HTTPException
        from src.api.v1.hub_tasks.router import get_task

        mock_repo.get_task.return_value = None
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await get_task(
                    task_id=uuid.uuid4(),
                    current_user=mock_user,
                    db=AsyncMock(),
                )

        assert exc_info.value.status_code == 404


class TestHubTasksRouterUpdate:
    async def test_update_existing_task(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import update_task
        from src.api.v1.hub_tasks.schemas import TaskUpdate

        body = TaskUpdate(title="Updated Title")
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await update_task(
                task_id=_FAKE_TASK_ID,
                body=body,
                current_user=mock_user,
                db=AsyncMock(),
            )

        mock_repo.update_task.assert_awaited_once()

    async def test_update_nonexistent_task_raises_404(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from fastapi import HTTPException
        from src.api.v1.hub_tasks.router import update_task
        from src.api.v1.hub_tasks.schemas import TaskUpdate

        mock_repo.update_task.return_value = None
        body = TaskUpdate(title="Something")
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await update_task(
                    task_id=uuid.uuid4(),
                    body=body,
                    current_user=mock_user,
                    db=AsyncMock(),
                )

        assert exc_info.value.status_code == 404


class TestHubTasksRouterDelete:
    async def test_cancel_existing_task_returns_none(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import cancel_task

        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await cancel_task(
                task_id=_FAKE_TASK_ID,
                current_user=mock_user,
                db=AsyncMock(),
            )

        assert result is None  # 204 No Content

    async def test_cancel_nonexistent_task_raises_404(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from fastapi import HTTPException
        from src.api.v1.hub_tasks.router import cancel_task

        mock_repo.cancel_task.return_value = False
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await cancel_task(
                    task_id=uuid.uuid4(),
                    current_user=mock_user,
                    db=AsyncMock(),
                )

        assert exc_info.value.status_code == 404


class TestHubTasksRouterHistory:
    async def test_get_history_returns_entries(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import get_task_history

        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await get_task_history(
                task_id=_FAKE_TASK_ID,
                current_user=mock_user,
                db=AsyncMock(),
            )

        assert len(result) == 1
        assert result[0].new_status == "todo"

    async def test_history_of_nonexistent_task_raises_404(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from fastapi import HTTPException
        from src.api.v1.hub_tasks.router import get_task_history

        mock_repo.get_task.return_value = None
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await get_task_history(
                    task_id=uuid.uuid4(),
                    current_user=mock_user,
                    db=AsyncMock(),
                )

        assert exc_info.value.status_code == 404


class TestHubTasksRouterDependencies:
    async def test_add_dependency_success(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from src.api.v1.hub_tasks.router import add_dependency
        from src.api.v1.hub_tasks.schemas import AddDependencyRequest

        dep_id = uuid.uuid4()
        body = AddDependencyRequest(depends_on_id=dep_id)
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            result = await add_dependency(
                task_id=_FAKE_TASK_ID,
                body=body,
                current_user=mock_user,
                db=AsyncMock(),
            )

        assert result["status"] == "created"

    async def test_add_duplicate_dependency_raises_409(self, mock_user: MagicMock, mock_repo: MagicMock) -> None:
        from fastapi import HTTPException
        from src.api.v1.hub_tasks.router import add_dependency
        from src.api.v1.hub_tasks.schemas import AddDependencyRequest

        mock_repo.add_dependency.return_value = False
        body = AddDependencyRequest(depends_on_id=uuid.uuid4())
        with patch("src.api.v1.hub_tasks.router.HubTaskRepository", return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await add_dependency(
                    task_id=_FAKE_TASK_ID,
                    body=body,
                    current_user=mock_user,
                    db=AsyncMock(),
                )

        assert exc_info.value.status_code == 409
