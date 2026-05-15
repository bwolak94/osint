from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import RefreshTokenModel
from src.core.ports.token_service import RefreshTokenRecord


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user_id: UUID, token_hash: str, family: str, expires_at: datetime, ip_address: str | None = None, user_agent: str | None = None) -> None:
        model = RefreshTokenModel(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            family=family,
            is_revoked=False,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return RefreshTokenRecord(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            family=model.family,
            is_revoked=model.is_revoked,
            created_at=model.created_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            ip_address=model.ip_address,
            user_agent=model.user_agent,
        )

    async def revoke(self, token_hash: str) -> bool:
        """Revoke the token with the given hash.

        Returns:
            ``True`` if a token was found and revoked; ``False`` if the hash
            was not found (already expired/deleted) or already revoked.
        """
        stmt = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def revoke_family(self, family: str) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.family == family, RefreshTokenModel.is_revoked == False)
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.is_revoked == False)
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)
        await self._session.flush()
