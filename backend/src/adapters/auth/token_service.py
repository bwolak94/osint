import hashlib
import secrets
import time
from uuid import UUID, uuid4

from jose import jwt, JWTError

from src.config import Settings
from src.core.ports.token_service import AccessTokenPayload, ITokenService


class JWTTokenService:
    """JWT-based token service implementation."""

    def __init__(self, settings: Settings):
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = settings.jwt_access_token_expire_minutes * 60

    def create_access_token(self, user_id: UUID, email: str, role: str, tier: str) -> str:
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "tier": tier,
            "iat": now,
            "exp": now + self._access_ttl,
            "type": "access",
            # jti is the unique token identifier used as the Redis blacklist key.
            # Storing only the jti (a UUID) instead of the full JWT saves ~90 % of
            # Redis memory per blacklisted token.
            "jti": uuid4().hex,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)

    def decode_access_token(self, token: str) -> AccessTokenPayload:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")

        if payload.get("type") != "access":
            raise ValueError("Not an access token")

        return AccessTokenPayload(
            sub=payload["sub"],
            email=payload["email"],
            role=payload["role"],
            subscription_tier=payload["tier"],
            exp=payload["exp"],
            jti=payload.get("jti", ""),  # graceful fallback for tokens issued before jti was added
        )

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
