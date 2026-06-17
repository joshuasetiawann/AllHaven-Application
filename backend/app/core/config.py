"""Centralized application settings.

All configuration is read from environment variables (or an optional local
``.env`` file). No secrets are hardcoded. See ``.env.example`` for the full list
of supported variables.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "CoreOS Command Center"
    APP_ENV: str = "local"
    API_V1_PREFIX: str = "/api/v1"
    # Comma-separated list (or JSON array) of allowed frontend origins.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    # --- Auth / security (local MVP auth boundary) ---
    SECRET_KEY: str = "dev-insecure-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_ALGORITHM: str = "HS256"

    # --- Database ---
    POSTGRES_USER: str = "coreos"
    POSTGRES_PASSWORD: str = "coreos"
    POSTGRES_DB: str = "coreos"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    # If empty, it is assembled from the POSTGRES_* values above.
    DATABASE_URL: str = ""

    # --- Optional integrations (never enabled by faking; see integration status) ---
    OLLAMA_BASE_URL: str = ""
    OLLAMA_DEFAULT_MODEL: str = ""
    N8N_BASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    WEATHER_API_KEY: str = ""

    # --- Secret storage (encryption at rest for web-configured credentials) ---
    # MVP scheme; document as replaceable by a KMS/Fernet in production.
    SETTINGS_ENCRYPTION_KEY: str = "change-me-32-byte-development-key"

    # --- Multi-provider AI system ---
    AI_DEFAULT_PROVIDER: str = "ollama"
    AI_ALLOW_EXTERNAL_PROVIDERS: bool = False
    AI_DEFAULT_PRIVACY_MODE: str = "local_private"
    # Optional env-level provider defaults (DB config takes precedence).
    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = ""
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_DEFAULT_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_DEFAULT_MODEL: str = ""
    GROK_API_KEY: str = ""
    GROK_DEFAULT_MODEL: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_DEFAULT_MODEL: str = ""

    @property
    def cors_origins(self) -> List[str]:
        """Parse BACKEND_CORS_ORIGINS into a list of origins."""
        raw = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            return json.loads(raw)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _assemble_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
