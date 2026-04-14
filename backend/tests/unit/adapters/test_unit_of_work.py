"""Tests for the Unit of Work pattern."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.adapters.db.unit_of_work import SQLAlchemyUnitOfWork


class TestSQLAlchemyUnitOfWork:
    @pytest.fixture
    def session_factory(self):
        session = AsyncMock()
        factory = MagicMock(return_value=session)
        return factory

    @pytest.mark.asyncio
    async def test_creates_repositories_on_enter(self, session_factory):
        uow = SQLAlchemyUnitOfWork(session_factory=session_factory)
        async with uow:
            assert uow.users is not None
            assert uow.investigations is not None
            assert uow.scan_results is not None

    @pytest.mark.asyncio
    async def test_commit_calls_session_commit(self, session_factory):
        uow = SQLAlchemyUnitOfWork(session_factory=session_factory)
        async with uow:
            await uow.commit()
        session = session_factory.return_value
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self, session_factory):
        uow = SQLAlchemyUnitOfWork(session_factory=session_factory)
        with pytest.raises(ValueError):
            async with uow:
                raise ValueError("test error")
        session = session_factory.return_value
        session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_session_closed_on_exit(self, session_factory):
        uow = SQLAlchemyUnitOfWork(session_factory=session_factory)
        async with uow:
            pass
        session = session_factory.return_value
        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graph_is_noop_without_neo4j(self, session_factory):
        uow = SQLAlchemyUnitOfWork(session_factory=session_factory, neo4j_driver=None)
        async with uow:
            # Should use NoOp graph repo
            node = await uow.graph.add_node(MagicMock())
            assert node is not None
