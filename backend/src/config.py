"""Application configuration loaded from environment variables."""

import warnings
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the OSINT platform backend."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Application
    app_name: str = "OSINT Platform"
    app_version: str = "0.1.0"
    debug: bool = False

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "osint"
    postgres_password: str = "osint"
    postgres_db: str = "osint"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"

    # MinIO / S3-compatible storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "osint-data"
    minio_secure: bool = False

    # JWT / Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_minutes: int = 10080  # 7 days
    jwt_refresh_token_expire_days: int = 7

    # Login protection
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # Crypto / Payments
    crypto_payment_provider_url: str = ""
    crypto_payment_api_key: str = ""
    crypto_webhook_secret: str = ""

    # Payment / NowPayments
    nowpayments_api_key: str = ""
    nowpayments_ipn_secret: str = ""
    nowpayments_sandbox: bool = True
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # External OSINT API keys
    shodan_api_key: str = ""
    hibp_api_key: str = ""
    virustotal_api_key: str = ""

    # OSINT settings
    osint_scan_timeout_seconds: int = 120
    osint_max_concurrent_scans: int = 5
    osint_default_scan_depth: int = 2

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # CORS
    cors_origins: list[str] = ["http://localhost:8080", "http://localhost:5173", "http://localhost:3000"]

    # Notification webhooks
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if not self.debug and self.jwt_secret_key == "change-me-in-production":
            warnings.warn(
                "SECURITY WARNING: JWT_SECRET_KEY is using the default value. "
                "Set a unique JWT_SECRET_KEY environment variable for production.",
                stacklevel=2,
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
