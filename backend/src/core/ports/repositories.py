"""Abstract repository interfaces for persistence."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.core.domain.entities.identity import Identity
from src.core.domain.entities.investigation import Investigation
from src.core.domain.entities.user import User


class IUserRepository(ABC):
    """Abstract repository for User persistence."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def create(self, user: User) -> User: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...

    @abstractmethod
    async def delete(self, user_id: UUID) -> None: ...


class IInvestigationRepository(ABC):
    """Abstract repository for Investigation persistence."""

    @abstractmethod
    async def get_by_id(self, investigation_id: UUID) -> Investigation | None: ...

    @abstractmethod
    async def list_by_owner(self, owner_id: UUID, offset: int = 0, limit: int = 50) -> list[Investigation]: ...

    @abstractmethod
    async def create(self, investigation: Investigation) -> Investigation: ...

    @abstractmethod
    async def update(self, investigation: Investigation) -> Investigation: ...

    @abstractmethod
    async def delete(self, investigation_id: UUID) -> None: ...


class IIdentityRepository(ABC):
    """Abstract repository for Identity persistence."""

    @abstractmethod
    async def get_by_id(self, identity_id: UUID) -> Identity | None: ...

    @abstractmethod
    async def list_by_investigation(self, investigation_id: UUID) -> list[Identity]: ...

    @abstractmethod
    async def create(self, identity: Identity) -> Identity: ...

    @abstractmethod
    async def update(self, identity: Identity) -> Identity: ...

    @abstractmethod
    async def delete(self, identity_id: UUID) -> None: ...
