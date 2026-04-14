"""SQLAlchemy + Neo4j Unit of Work implementation."""

from typing import Self

from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.db.repositories import SqlAlchemyInvestigationRepository, SqlAlchemyUserRepository
from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository
from src.adapters.graph.neo4j_store import Neo4jGraphRepository


class SQLAlchemyUnitOfWork:
    """Coordinates PostgreSQL (via SQLAlchemy) and Neo4j transactions.

    PostgreSQL is the source of truth. Neo4j is a denormalized read model
    that can be rebuilt from PG data. There is no distributed transaction;
    PG commits first, then Neo4j operations are idempotent (MERGE).
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        neo4j_driver: AsyncDriver | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._neo4j_driver = neo4j_driver
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self._session)
        self.investigations = SqlAlchemyInvestigationRepository(self._session)
        self.scan_results = SqlAlchemyScanResultRepository(self._session)

        if self._neo4j_driver is not None:
            self.graph = Neo4jGraphRepository(self._neo4j_driver)
        else:
            self.graph = _NoOpGraphRepository()

        # identities placeholder
        self.identities = None  # type: ignore[assignment]

        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        if self._session is not None:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()


class _NoOpGraphRepository:
    """Placeholder graph repository when Neo4j is not available."""

    async def add_node(self, node):
        return node

    async def add_edge(self, edge):
        return edge

    async def get_subgraph(self, investigation_id, depth=3):
        return [], []

    async def find_paths(self, source_id, target_id, max_depth=5):
        return []
