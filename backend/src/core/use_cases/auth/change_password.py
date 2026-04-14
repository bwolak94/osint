"""Use case: change a user's password and revoke all sessions."""

from uuid import UUID

from src.core.domain.events.auth import PasswordChanged
from src.core.ports.event_publisher import IEventPublisher
from src.core.ports.password_hasher import IPasswordHasher
from src.core.ports.repositories import IUserRepository
from src.core.ports.token_service import IRefreshTokenRepository
from src.core.use_cases.auth.exceptions import AuthenticationError


class ChangePasswordCommand:
    def __init__(self, user_id: UUID, current_password: str, new_password: str):
        self.user_id = user_id
        self.current_password = current_password
        self.new_password = new_password


class ChangePasswordUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        password_hasher: IPasswordHasher,
        refresh_token_repo: IRefreshTokenRepository,
        event_publisher: IEventPublisher,
    ):
        self._user_repo = user_repo
        self._password_hasher = password_hasher
        self._refresh_repo = refresh_token_repo
        self._event_publisher = event_publisher

    async def execute(self, command: ChangePasswordCommand) -> None:
        user = await self._user_repo.get_by_id(command.user_id)
        if user is None:
            raise ValueError("User not found")

        if not self._password_hasher.verify(command.current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")

        new_hash = self._password_hasher.hash(command.new_password)
        updated = user.change_password(new_hash)
        await self._user_repo.save(updated)

        # Revoke all refresh tokens (force re-login on all devices)
        await self._refresh_repo.revoke_all_for_user(command.user_id)

        await self._event_publisher.publish(PasswordChanged(user_id=command.user_id))
