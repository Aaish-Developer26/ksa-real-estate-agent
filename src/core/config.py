"""Loads and validates application configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.logging_setup import get_logger

logger = get_logger(__name__)


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and ``.env``.

    Attributes:
        groq_api_key: API key for the Groq LLM provider.
        litellm_model: The active LiteLLM model identifier.
        google_api_key: Optional API key for the Gemini backup LLM provider.
        langsmith_api_key: API key for LangSmith tracing.
        langsmith_project: LangSmith project name for trace grouping.
        langchain_tracing_v2: Whether LangChain v2 tracing is enabled.
        brave_search_api_key: API key for the Brave Search MCP server.
        postgres_url: Full Postgres connection URL, including credentials.
        postgres_user: Postgres username.
        postgres_password: Postgres password.
        postgres_db: Postgres database name.
        redis_url: Redis connection URL for Celery broker/backend and cache.
        app_env: Deployment environment.
        log_level: Minimum log level for the structured JSON logger.
    """

    # LLM Configuration
    groq_api_key: SecretStr
    litellm_model: str = "groq/llama-3.1-70b-versatile"
    google_api_key: SecretStr | None = None

    # Observability
    langsmith_api_key: SecretStr
    langsmith_project: str = "riyadh-re-agent"
    langchain_tracing_v2: bool = True

    # Search
    brave_search_api_key: SecretStr

    # Database
    postgres_url: SecretStr
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str

    # Cache & Queue
    redis_url: str = "redis://redis:6379/0"

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Returns:
        The process-wide ``Settings`` instance, constructed once from
        environment variables and the ``.env`` file.
    """
    settings = Settings()  # type: ignore[call-arg]
    logger.info(
        "Configuration loaded: app_env=%s log_level=%s litellm_model=%s "
        "langsmith_project=%s",
        settings.app_env,
        settings.log_level,
        settings.litellm_model,
        settings.langsmith_project,
    )
    return settings


get_settings()
