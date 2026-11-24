# ============================================================
# app/config.py — Centralized Application Configuration
#
# ARCHITECT'S NOTE:
#   All configuration is loaded from environment variables using
#   Pydantic Settings. This enforces the "12-factor app" principle:
#   config lives in the environment, NOT hardcoded in source code.
#
#   In development: values come from your .env file
#   In production:  values come from Kubernetes Secrets / Docker secrets
#
#   The Settings class is a singleton — import `settings` anywhere
#   in the app and you get the same object.
# ============================================================

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """
    Pydantic Settings model that reads from environment variables.
    Every field here must have a matching entry in .env.example.
    """

    # -------------------------------------------------------
    # App
    # -------------------------------------------------------
    app_name: str = "Enterprise AI Gateway"
    environment: str = "development"
    debug: bool = False
    secret_key: str                             # required — no default

    # -------------------------------------------------------
    # Database (PostgreSQL)
    # -------------------------------------------------------
    database_url: str                           # full connection string
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "enterprise_ai"
    postgres_user: str = "ai_user"
    postgres_password: str

    # -------------------------------------------------------
    # Cache (Redis)
    # -------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # -------------------------------------------------------
    # JWT Authentication
    # -------------------------------------------------------
    jwt_secret_key: str                         # required — no default
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # -------------------------------------------------------
    # LiteLLM Proxy
    # -------------------------------------------------------
    litellm_proxy_url: str = "http://litellm:4000"
    litellm_master_key: str                     # required — no default

    # -------------------------------------------------------
    # LLM Provider Keys (passed through to LiteLLM config)
    # -------------------------------------------------------
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    mistral_api_key: str = ""

    # -------------------------------------------------------
    # CORS
    # -------------------------------------------------------
    # Stored as a comma-separated string in .env, parsed into a list here
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a Python list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    # -------------------------------------------------------
    # Pydantic Settings configuration
    # -------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",            # read from .env in development
        env_file_encoding="utf-8",
        case_sensitive=False,       # DATABASE_URL and database_url both work
        extra="ignore",             # ignore extra env vars we don't declare here
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings singleton.
    Using lru_cache means the .env file is only read once at startup,
    not on every request — important for performance in production.
    """
    return Settings()


# Module-level singleton — import this wherever you need config
settings = get_settings()
