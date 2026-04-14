"""SQLAlchemy implementations of repository ports."""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import InvestigationModel, UserModel
from src.core.domain.entities.investigation import Investigation, InvestigationStatus
from src.core.domain.entities.types import ScanInputType, SeedInput
from src.core.domain.entities.user import User
from src.core.domain.value_objects.email import Email
from src.core.ports.repositories import IInvestigationRepository, IUserRepository


class SqlAlchemyUserRepository(IUserRepository):
    """User repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: Email) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, user: User) -> User:
        """Upsert pattern: update if user exists, otherwise create."""
        model = await self._session.get(UserModel, user.id)
        if model is not None:
            model.email = str(user.email)
            model.hashed_password = user.hashed_password
            model.role = user.role
            model.subscription_tier = user.subscription_tier
            model.is_active = user.is_active
            model.is_email_verified = user.is_email_verified
            model.failed_login_attempts = user.failed_login_attempts
            model.locked_until = user.locked_until
            model.last_login_at = user.last_login_at
        else:
            model = UserModel(
                id=user.id,
                email=str(user.email),
                hashed_password=user.hashed_password,
                role=user.role,
                subscription_tier=user.subscription_tier,
                is_active=user.is_active,
                is_email_verified=user.is_email_verified,
                failed_login_attempts=user.failed_login_attempts,
                locked_until=user.locked_until,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
            )
            self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            email=str(user.email),
            hashed_password=user.hashed_password,
            role=user.role,
            subscription_tier=user.subscription_tier,
            is_active=user.is_active,
            is_email_verified=user.is_email_verified,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise ValueError(f"User {user.id} not found")
        model.email = str(user.email)
        model.hashed_password = user.hashed_password
        model.role = user.role
        model.subscription_tier = user.subscription_tier
        model.is_active = user.is_active
        model.is_email_verified = user.is_email_verified
        model.failed_login_attempts = user.failed_login_attempts
        model.locked_until = user.locked_until
        model.last_login_at = user.last_login_at
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
            email=Email(model.email),
            hashed_password=model.hashed_password,
            role=model.role,
            subscription_tier=model.subscription_tier,
            is_active=model.is_active,
            is_email_verified=model.is_email_verified,
            failed_login_attempts=model.failed_login_attempts,
            locked_until=model.locked_until,
            last_login_at=model.last_login_at,
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

    async def save(self, investigation: Investigation) -> Investigation:
        """Upsert pattern: update if investigation exists, otherwise create."""
        model = await self._session.get(InvestigationModel, investigation.id)
        if model is not None:
            model.title = investigation.title
            model.description = investigation.description
            model.status = investigation.status
            model.seed_inputs = [
                {"value": s.value, "type": s.input_type.value}
                for s in investigation.seed_inputs
            ]
            model.tags = list(investigation.tags)
            model.updated_at = investigation.updated_at
            model.completed_at = investigation.completed_at
        else:
            model = InvestigationModel(
                id=investigation.id,
                owner_id=investigation.owner_id,
                title=investigation.title,
                description=investigation.description,
                status=investigation.status,
                seed_inputs=[
                    {"value": s.value, "type": s.input_type.value}
                    for s in investigation.seed_inputs
                ],
                tags=list(investigation.tags),
                created_at=investigation.created_at,
                updated_at=investigation.updated_at,
                completed_at=investigation.completed_at,
            )
            self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def create(self, investigation: Investigation) -> Investigation:
        model = InvestigationModel(
            id=investigation.id,
            title=investigation.title,
            description=investigation.description,
            status=investigation.status,
            owner_id=investigation.owner_id,
            seed_inputs=[
                {"value": s.value, "type": s.input_type.value}
                for s in investigation.seed_inputs
            ],
            tags=list(investigation.tags),
            created_at=investigation.created_at,
            updated_at=investigation.updated_at,
            completed_at=investigation.completed_at,
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
        model.seed_inputs = [
            {"value": s.value, "type": s.input_type.value}
            for s in investigation.seed_inputs
        ]
        model.tags = list(investigation.tags)
        model.updated_at = investigation.updated_at
        model.completed_at = investigation.completed_at
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, investigation_id: UUID) -> None:
        model = await self._session.get(InvestigationModel, investigation_id)
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def list_by_owner_cursor(
        self, owner_id: UUID, cursor: UUID | None = None, limit: int = 20
    ) -> tuple[list[Investigation], bool]:
        """Cursor-based pagination. Returns (items, has_next)."""
        conditions = [InvestigationModel.owner_id == owner_id]
        if cursor is not None:
            # Fetch the cursor item's created_at for comparison
            cursor_model = await self._session.get(InvestigationModel, cursor)
            if cursor_model is not None:
                conditions.append(
                    (InvestigationModel.created_at < cursor_model.created_at)
                    | (
                        (InvestigationModel.created_at == cursor_model.created_at)
                        & (InvestigationModel.id < cursor)
                    )
                )

        stmt = (
            select(InvestigationModel)
            .where(and_(*conditions))
            .order_by(
                InvestigationModel.created_at.desc(),
                InvestigationModel.id.desc(),
            )
            .limit(limit + 1)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        has_next = len(models) > limit
        if has_next:
            models = models[:limit]

        return [self._to_entity(m) for m in models], has_next

    @staticmethod
    def _to_entity(model: InvestigationModel) -> Investigation:
        seed_inputs: list[SeedInput] = []
        if model.seed_inputs:
            for s in model.seed_inputs:
                if isinstance(s, dict):
                    seed_inputs.append(
                        SeedInput(
                            value=s.get("value", ""),
                            input_type=ScanInputType(
                                s.get("type", s.get("input_type", "email"))
                            ),
                        )
                    )

        tags = frozenset(model.tags) if model.tags else frozenset()

        return Investigation(
            id=model.id,
            owner_id=model.owner_id,
            title=model.title,
            description=model.description,
            status=InvestigationStatus(model.status),
            seed_inputs=seed_inputs,
            tags=tags,
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )
