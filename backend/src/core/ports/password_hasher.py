"""Port for password hashing and verification."""

from typing import Protocol


class IPasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hashed: str) -> bool: ...
