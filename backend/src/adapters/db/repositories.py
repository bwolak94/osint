"""SQLAlchemy implementations of repository ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import InvestigationModel, UserModel
from src.core.domain.entities.investigation import Investigation, InvestigationStatus
from src.core.domain.entities.user import User
from src.core.ports.repositories import IInvestigationRepository, IUserRepository


class SqlAlchemyUserRepository(IUserRepository):
    """User repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise ValueError(f"User {user.id} not found")
        model.email = user.email
        model.hashed_password = user.hashed_password
        model.is_active = user.is_active
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, user_id: UUID) -> None:
        model = await self._session.get(UserModel, user_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            hashed_password=model.hashed_password,
            is_active=model.is_active,
            created_at=model.created_at,
        )


class SqlAlchemyInvestigationRepository(IInvestigationRepository):
    """Investigation repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, investigation_id: UUID) -> Investigation | None:
        model = await self._session.get(InvestigationModel, investigation_id)
        return self._to_entity(model) if model else None

    async def list_by_owner(self, owner_id: UUID, offset: int = 0, limit: int = 50) -> list[Investigation]:
        stmt = (
            select(InvestigationModel)
            .where(InvestigationModel.owner_id == owner_id)
            .order_by(InvestigationModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def create(self, investigation: Investigation) -> Investigation:
        model = InvestigationModel(
            id=investigation.id,
            title=investigation.title,
            description=investigation.description,
            status=investigation.status,
            owner_id=investigation.owner_id,
            created_at=investigation.created_at,
            updated_at=investigation.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, investigation: Investigation) -> Investigation:
        model = await self._session.get(InvestigationModel, investigation.id)
        if model is None:
            raise ValueError(f"Investigation {investigation.id} not found")
        model.title = investigation.title
        model.description = investigation.description
        model.status = investigation.status
        model.updated_at = investigation.updated_at
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, investigation_id: UUID) -> None:
        model = await self._session.get(InvestigationModel, investigation_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()

    @staticmethod
    def _to_entity(model: InvestigationModel) -> Investigation:
        return Investigation(
            id=model.id,
            title=model.title,
            description=model.description,
            status=InvestigationStatus(model.status),
            owner_id=model.owner_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
