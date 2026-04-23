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

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_prefix: str = "osint"
    elasticsearch_username: str = ""
    elasticsearch_password: str = ""

    # JWT / Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_minutes: int = 10080  # 7 days
    jwt_refresh_token_expire_days: int = 7

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

    # Security
    pii_encryption_key: str = ""
    ip_allowlist: list[str] = []
    ip_allowlist_enabled: bool = False

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
