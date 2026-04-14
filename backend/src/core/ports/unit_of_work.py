"""Unit of Work port for coordinating transactions across repositories."""

from typing import Protocol, Self

from src.core.ports.repositories import (
    IGraphRepository,
    IIdentityRepository,
    IInvestigationRepository,
    IUserRepository,
)
from src.core.ports.scan_result_repository import IScanResultRepository


class IUnitOfWork(Protocol):
    """Coordinates commits and rollbacks across multiple repositories.

    Usage:
        async with uow:
            inv = await uow.investigations.get_by_id(inv_id)
            await uow.investigations.save(inv)
            await uow.graph.add_node(node)
            await uow.commit()
    """

    users: IUserRepository
    investigations: IInvestigationRepository
    identities: IIdentityRepository
    scan_results: IScanResultRepository
    graph: IGraphRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
