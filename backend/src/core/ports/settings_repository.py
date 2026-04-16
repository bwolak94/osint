"""Repository ports for settings persistence."""

from typing import Protocol
from uuid import UUID

from src.core.domain.entities.settings import SystemSettings, UserSettings


class IUserSettingsRepository(Protocol):
    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None: ...
    async def save(self, settings: UserSettings) -> UserSettings: ...
    async def delete(self, user_id: UUID) -> None: ...


class ISystemSettingsRepository(Protocol):
    async def get(self) -> SystemSettings: ...
    async def save(self, settings: SystemSettings) -> SystemSettings: ...
