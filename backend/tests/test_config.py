"""Tests for Pydantic Settings configuration."""

import pytest

from src.config import Settings


class TestSettings:
    """Verify that Settings correctly loads values from environment variables."""

    def test_default_values(self) -> None:
        """Settings should have sensible defaults when no env vars are set."""
        settings = Settings()
        assert settings.app_name == "OSINT Platform"
        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.redis_port == 6379
        assert settings.jwt_algorithm == "HS256"
        assert settings.rate_limit_requests == 100

    def test_postgres_dsn_construction(self) -> None:
        """The postgres_dsn property should build a valid async DSN."""
        settings = Settings(
            postgres_user="u",
            postgres_password="p",
            postgres_host="db.example.com",
            postgres_port=5433,
            postgres_db="mydb",
        )
        assert settings.postgres_dsn == "postgresql+asyncpg://u:p@db.example.com:5433/mydb"

    def test_redis_url_without_password(self) -> None:
        """Redis URL should omit auth when no password is set."""
        settings = Settings(redis_host="cache", redis_port=6380, redis_password="", redis_db=1)
        assert settings.redis_url == "redis://cache:6380/1"

    def test_redis_url_with_password(self) -> None:
        """Redis URL should include auth when a password is provided."""
        settings = Settings(redis_host="cache", redis_port=6380, redis_password="secret", redis_db=2)
        assert settings.redis_url == "redis://:secret@cache:6380/2"

    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings should be overridden by environment variables."""
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("POSTGRES_HOST", "pg.test")
        monkeypatch.setenv("POSTGRES_PORT", "9999")
        monkeypatch.setenv("JWT_SECRET_KEY", "super-secret")
        monkeypatch.setenv("RATE_LIMIT_REQUESTS", "500")
        monkeypatch.setenv("DEBUG", "true")

        settings = Settings()

        assert settings.app_name == "Test App"
        assert settings.postgres_host == "pg.test"
        assert settings.postgres_port == 9999
        assert settings.jwt_secret_key == "super-secret"
        assert settings.rate_limit_requests == 500
        assert settings.debug is True

    def test_cors_origins_default(self) -> None:
        """Default CORS origins should include localhost:3000."""
        settings = Settings()
        assert "http://localhost:3000" in settings.cors_origins
