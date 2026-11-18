"""Application configuration. Secrets come only from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TradeFlow"
    environment: str = "development"  # development | test | production
    database_url: str = "postgresql+psycopg://tradeflow:tradeflow@db:5432/tradeflow"

    jwt_secret: str = "change-me-in-env"  # MUST be overridden outside development
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Rate limiting (requests per window per client IP) for sensitive endpoints
    auth_rate_limit: int = 20
    auth_rate_window_seconds: int = 60

    # Upload limits
    max_upload_mb: int = 10

    # LLM provider abstraction. Empty provider => deterministic assistant only.
    llm_provider: str = ""  # "" | "openai_compatible" | "anthropic"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 30

    # Bootstrap super admin (created by seed if absent)
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = ""

    timezone: str = "Asia/Tashkent"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
