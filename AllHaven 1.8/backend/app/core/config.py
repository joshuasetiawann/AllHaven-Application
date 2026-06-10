"""Centralized application settings.

All configuration is read from environment variables (or an optional local
``.env`` file). No secrets are hardcoded. See ``.env.example`` for the full list
of supported variables.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env locations relative to this file so it works from any CWD.
# Priority (lowest → highest): repo-root .env, then backend/.env, then real
# environment variables. This lets users edit a single .env at the repo root and
# have the web app's Settings pick those values up as defaults.
_CONFIG_FILE = Path(__file__).resolve()
_BACKEND_DIR = _CONFIG_FILE.parents[2]  # .../backend
_REPO_ROOT = _CONFIG_FILE.parents[3]  # repo root
_ENV_FILES = (str(_REPO_ROOT / ".env"), str(_BACKEND_DIR / ".env"))


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "AllHaven Command Center"
    APP_ENV: str = "local"
    API_V1_PREFIX: str = "/api/v1"
    # Comma-separated list (or JSON array) of allowed frontend origins.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
    # Allow any origin (no cookies; bearer-token auth only). Auto-on in local mode
    # so the app is reachable from any device on your LAN without listing IPs.
    BACKEND_CORS_ALLOW_ALL: bool = False

    # --- Auth / security (local MVP auth boundary) ---
    SECRET_KEY: str = "dev-insecure-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_ALGORITHM: str = "HS256"

    # --- Database ---
    POSTGRES_USER: str = "allhaven"
    POSTGRES_PASSWORD: str = "allhaven"
    POSTGRES_DB: str = "allhaven"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    # If empty, it is assembled from the POSTGRES_* values above.
    DATABASE_URL: str = ""

    # --- Optional integrations (never enabled by faking; see integration status) ---
    OLLAMA_BASE_URL: str = ""
    OLLAMA_DEFAULT_MODEL: str = ""
    N8N_BASE_URL: str = ""
    N8N_API_KEY: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_REDIRECT_URI: str = ""
    WEATHER_API_KEY: str = ""
    WEATHER_PROVIDER: str = ""
    DRIVE_STORAGE_PROVIDER: str = ""
    # Local Drive storage root for uploaded file bytes (metadata lives in the DB).
    DRIVE_STORAGE_DIR: str = ""
    # Override the .env mirror path (tests point this at a temp file so the real
    # repo .env is never touched).
    ENV_SYNC_PATH: str = ""

    # --- Google OAuth foundation (login + scoped API access) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/oauth/google/callback"

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
    BLACKBOX_API_KEY: str = ""
    BLACKBOX_DEFAULT_MODEL: str = ""
    # Legacy single OpenRouter key (kept for backward compatibility).
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_DEFAULT_MODEL: str = ""
    # Three independent OpenRouter agent slots.
    OPENROUTER_1_API_KEY: str = ""
    OPENROUTER_1_DEFAULT_MODEL: str = ""
    OPENROUTER_2_API_KEY: str = ""
    OPENROUTER_2_DEFAULT_MODEL: str = ""
    OPENROUTER_3_API_KEY: str = ""
    OPENROUTER_3_DEFAULT_MODEL: str = ""

    @property
    def drive_storage_path(self) -> str:
        """Absolute Drive storage root (defaults to <repo>/var/drive)."""
        return self.DRIVE_STORAGE_DIR or str(_REPO_ROOT / "var" / "drive")

    @property
    def env_file_path(self) -> str:
        """Absolute path of the .env that web Settings may mirror to."""
        return self.ENV_SYNC_PATH or str(_REPO_ROOT / ".env")

    @property
    def is_local_env(self) -> bool:
        """True in local/development mode, where writing back to .env is allowed."""
        return (self.APP_ENV or "").strip().lower() in ("local", "dev", "development")

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
