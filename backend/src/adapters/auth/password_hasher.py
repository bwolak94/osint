"""Password hasher using bcrypt directly (avoids passlib/bcrypt version conflicts)."""

import bcrypt


class BcryptPasswordHasher:
    """Password hasher using bcrypt with 12 rounds."""

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(self._rounds)).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
