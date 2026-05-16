"""Application configuration loaded from environment variables."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
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

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "osint"
    elasticsearch_username: str = ""
    elasticsearch_password: str = ""

    # JWT / Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    @property
    def jwt_refresh_token_expire_minutes(self) -> int:
        """Derived from jwt_refresh_token_expire_days — single source of truth."""
        return self.jwt_refresh_token_expire_days * 24 * 60

    # Mock data mode: when True, OSINT endpoints return deterministic demo data.
    # Defaults to False — set OSINT_MOCK_DATA=true only for demos/development. (#13)
    osint_mock_data: bool = False

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "OSINT Platform"
    webauthn_origin: str = "http://localhost:5173"

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
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    cors_allow_headers: list[str] = [
        "Authorization",
        "Content-Type",
        "X-Correlation-ID",
        "X-Request-ID",
        "Accept",
        "Origin",
    ]

    # HITL (Human-in-the-loop) gate
    hitl_timeout_minutes: int = 30
    hitl_poll_interval_seconds: int = 5

    # Scanner settings
    scanner_default_timeout_seconds: int = 120
    scanner_rate_limit_counts_as_failure: bool = False  # don't trip CB on rate limits

    # Circuit breaker (Redis-backed)
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: int = 300

    # Anomaly detection
    anomaly_result_threshold: int = 50  # flag scanners returning more than this many results

    # Notification webhooks
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # LLM / AI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    llm_provider: str = "openai"  # "openai" or "anthropic"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7

    # SIEM
    siem_endpoint: str = ""
    siem_api_key: str = ""
    siem_type: str = "splunk"  # splunk, elastic_siem, sentinel

    # MISP
    misp_url: str = ""
    misp_api_key: str = ""
    misp_verify_ssl: bool = True

    # TheHive
    thehive_url: str = ""
    thehive_api_key: str = ""

    # Jira
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    # Database connection pool (passed to SQLAlchemy create_async_engine)
    db_pool_size: int = 20
    db_pool_max_overflow: int = 10

    # Celery worker tuning
    # worker_prefetch_multiplier=1 is safest for long-running I/O-bound tasks (no greedy pre-fetch).
    # Raise to 4-8 for very short tasks to improve throughput. (#33)
    celery_worker_prefetch_multiplier: int = 1

    @model_validator(mode="after")
    def _validate_db_pool_size(self) -> "Settings":
        """Warn when total DB connections may exceed PostgreSQL max_connections."""
        total = (self.db_pool_size + self.db_pool_max_overflow) * 4  # 4 Uvicorn workers
        if total > 90:
            import warnings
            warnings.warn(
                f"DB pool configuration may exceed PostgreSQL max_connections: "
                f"(db_pool_size={self.db_pool_size} + db_pool_max_overflow={self.db_pool_max_overflow}) "
                f"* 4 workers = {total} connections. Default max_connections=100. "
                "Reduce pool sizes or raise max_connections.",
                stacklevel=2,
            )
        return self

    # Security
    pii_encryption_key: str = ""
    ip_allowlist: list[str] = []
    ip_allowlist_enabled: bool = False

    # Metrics endpoint protection (#36)
    # Set to a random secret; configure Prometheus to send it as Bearer token.
    # Leave empty to allow unauthenticated access (safe in private networks).
    metrics_api_key: str = ""

    # GitHub
    github_api_token: str = ""

    # OPSEC / Proxy settings
    proxy_mode: str = "direct"          # "direct" | "tor" | "socks5" | "rotating"
    socks5_proxy_url: str = ""          # e.g. "socks5://user:pass@host:1080"
    socks5_proxy_pool: list[str] = []   # Proxy rotation pool (rotating mode)
    tor_proxy_port: int = 9050          # Tor SOCKS5 port (localhost)

    # Tracking code pivot
    spyonweb_api_key: str = ""          # https://spyonweb.com/api

    # New scanner API keys
    serpapi_api_key: str = ""           # Google Dorking via SerpAPI
    etherscan_api_key: str = ""         # Ethereum address tracing
    abuseipdb_api_key: str = ""         # IOC enrichment
    otx_api_key: str = ""               # AlienVault OTX
    opencti_url: str = ""               # OpenCTI instance URL
    opencti_api_token: str = ""         # OpenCTI API token
    slack_bot_token: str = ""           # Slack bot OAuth token
    slack_signing_secret: str = ""      # Slack request signature verification
    greynoise_api_key: str = ""         # GreyNoise Community API key

    # Facebook Intel — optional authenticated session
    # Export cookies from a logged-in browser session as a JSON array and paste here.
    # Without this, only public pages / search results are accessible.
    fb_session_cookies: str = ""        # JSON array of cookie dicts (name/value/domain/path)

    # IP enrichment / DNS scanner API keys (batch 3)
    urlscan_api_key: str = ""           # urlscan.io — optional, unlocks higher rate limits
    viewdns_api_key: str = ""           # viewdns.info — required for JSON API
    ipinfo_api_key: str = ""            # ipinfo.io — 50k/month free with key

    # Additional scanner API keys (batch 4+)
    opencorporates_api_key: str = ""    # Free academic — opencorporates.com
    companies_house_api_key: str = ""   # Free — developer.company-information.service.gov.uk
    bevigil_api_key: str = ""           # Free tier — bevigil.com
    marinetraffic_api_key: str = ""     # Marine vessel tracking
    aishub_username: str = ""           # AIS vessel tracking hub
    nuclei_templates_path: str = ""     # Path to local nuclei templates directory
    theharvester_path: str = ""         # Path to theHarvester installation

    # Multi-region routing
    preferred_scan_regions: list[str] = ["default"]

    # Data retention defaults
    default_investigation_retention_days: int = 365
    default_scan_result_retention_days: int = 90
    cold_archive_bucket: str = "osint-cold-archive"

    # PentAI LLM configuration (Ollama)
    pentest_llm_planner_model: str = "llama3.2:3b"
    pentest_llm_reporter_model: str = "llama3.2:3b"
    ollama_host: str = "http://ollama:11434"

    # GitHub integration (format: "owner/repo")
    github_repo: str = ""

    # Pentest active poisoning (disabled by default for safety)
    pentest_enable_active_poisoning: bool = False

    # SMTP — used for phishing simulation email delivery
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "pentest@localhost"

    # ── Hub AI Productivity ───────────────────────────────────────────────────
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_collection_knowledge: str = "knowledge"

    # LangSmith observability (optional — set to enable tracing)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "hub-production"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # LangSmith observability (Phase 1.6)
    langsmith_api_key: str | None = None
    langsmith_project: str = "hub-agent"
    langsmith_tracing_enabled: bool = False

    # Hub task settings
    hub_task_ttl_seconds: int = 3600
    hub_max_steps: int = 10
    hub_sandbox_image: str = "hub-agent-sandbox:hardened"
    hub_sandbox_network: str = "sandbox-net"
    hub_sandbox_timeout_seconds: int = 300

    # Tavily (Phase 2 — web research)
    tavily_api_key: str = ""

    # Google Calendar MCP (Phase 3 — HTTP/SSE only, STDIO banned)
    google_calendar_mcp_url: str = "https://mcp.googleapis.com/calendar/sse"
    google_calendar_oauth_token: str = ""

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
        if v not in allowed:
            raise ValueError(f"JWT_ALGORITHM must be one of {sorted(allowed)}, got '{v}'")
        return v

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError("REDIS_URL must start with redis://, rediss://, or unix://")
        return v

    @field_validator("neo4j_uri")
    @classmethod
    def _validate_neo4j_uri(cls, v: str) -> str:
        if not v.startswith(("bolt://", "bolt+s://", "neo4j://", "neo4j+s://")):
            raise ValueError("NEO4J_URI must start with bolt:// or neo4j://")
        return v

    @field_validator("postgres_host")
    @classmethod
    def _validate_postgres_host(cls, v: str) -> str:
        if not v:
            raise ValueError("POSTGRES_HOST must not be empty")
        return v

    @model_validator(mode="after")
    def _validate_postgres_dsn_format(self) -> "Settings":
        parsed = urlparse(self.postgres_dsn)
        if not parsed.hostname:
            raise ValueError(f"Invalid PostgreSQL DSN: hostname missing in '{self.postgres_dsn}'")
        return self

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if not self.debug and self.jwt_secret_key == "change-me-in-production":
            raise ValueError(
                "SECURITY ERROR: JWT_SECRET_KEY is using the default value. "
                "Set a unique JWT_SECRET_KEY environment variable for production."
            )
        if not self.debug and len(self.jwt_secret_key) < 32:
            raise ValueError(
                "SECURITY ERROR: JWT_SECRET_KEY is too short. "
                "Use at least 32 characters for adequate security."
            )
        if not self.debug and self.pii_encryption_key and len(self.pii_encryption_key) < 32:
            raise ValueError(
                "SECURITY ERROR: PII_ENCRYPTION_KEY is too short. "
                "Use at least 32 bytes for adequate security."
            )
        if not self.debug and self.neo4j_password == "neo4j":
            raise ValueError(
                "SECURITY ERROR: NEO4J_PASSWORD is using the default value. "
                "Set a strong NEO4J_PASSWORD in production."
            )
        if not self.debug and self.minio_access_key == "minioadmin":
            raise ValueError(
                "SECURITY ERROR: MINIO_ACCESS_KEY is using the default value. "
                "Set a strong MINIO_ACCESS_KEY in production."
            )
        if not self.debug and self.minio_secret_key == "minioadmin":
            raise ValueError(
                "SECURITY ERROR: MINIO_SECRET_KEY is using the default value. "
                "Set a strong MINIO_SECRET_KEY in production."
            )
        if not self.debug:
            localhost_origins = [
                o for o in self.cors_origins
                if "localhost" in o or "127.0.0.1" in o
            ]
            if localhost_origins:
                raise ValueError(
                    f"SECURITY ERROR: CORS_ORIGINS contains localhost entries in production: "
                    f"{localhost_origins}. Remove them or set DEBUG=true."
                )
        # A wildcard origin combined with allow_credentials=True is forbidden by
        # the CORS spec and will be silently rejected by all modern browsers.
        # Raise at startup so the misconfiguration is caught immediately. (#11)
        if "*" in self.cors_origins:
            raise ValueError(
                "SECURITY ERROR: CORS_ORIGINS contains '*' (wildcard). "
                "Wildcard origin is incompatible with allow_credentials=True. "
                "Specify explicit allowed origins instead."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


def reset_settings() -> None:
    """Clear the cached Settings instance.

    Useful in tests that patch environment variables after module import:
        monkeypatch.setenv("DEBUG", "true")
        reset_settings()
        settings = get_settings()  # picks up the patched env
    """
    get_settings.cache_clear()
