from passlib.context import CryptContext


class BcryptPasswordHasher:
    """Password hasher using bcrypt with 12 rounds."""

    def __init__(self) -> None:
        self._context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

    def hash(self, password: str) -> str:
        return self._context.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        return self._context.verify(password, hashed)
