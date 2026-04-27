"""Seed script — creates the default admin user if it doesn't exist.

Run inside the API container:
    docker compose exec api python -m src.scripts.seed_admin
"""

import asyncio
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import async_session_factory
from src.adapters.db.models import UserModel
from src.core.domain.entities.types import SubscriptionTier, UserRole

DEFAULT_USERS = [
    {"email": "admin@osint.platform", "password": "admin", "role": UserRole.ADMIN},
    {"email": "kolak3877@gmail.com", "password": "admin", "role": UserRole.ADMIN},
]


async def _create_user(session: AsyncSession, email: str, password: str, role: UserRole) -> None:
    existing = await session.scalar(select(UserModel).where(UserModel.email == email))
    if existing is not None:
        print(f"[seed] already exists: {email}")
        return

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
    now = datetime.now(timezone.utc)
    user = UserModel(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hashed,
        role=role,
        subscription_tier=SubscriptionTier.ENTERPRISE,
        is_active=True,
        is_email_verified=True,
        failed_login_attempts=0,
        created_at=now,
    )
    session.add(user)
    await session.commit()
    print(f"[seed] created: {email} / {password}")


async def seed() -> None:
    async with async_session_factory() as session:
        for u in DEFAULT_USERS:
            await _create_user(session, u["email"], u["password"], u["role"])


if __name__ == "__main__":
    asyncio.run(seed())
