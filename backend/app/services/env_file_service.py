"""Local .env mirror service.

The database is the runtime source of truth for web-configured settings. As a
developer convenience, allowed keys are ALSO mirrored into the repo-root ``.env``
so the values survive a process restart and are visible to CLI tooling.

Safety rules (all enforced here):
    * Only writes in local/development mode (``APP_ENV`` in local/dev/development).
    * Only an explicit allowlist of keys may be written — never arbitrary keys.
    * A timestamped backup (``.env.bak.<ts>``) is created before each write.
    * Writes are atomic (temp file + ``os.replace``) and chmod 0600 where possible.
    * Unrelated existing keys/comments are preserved; keys are never duplicated.
    * Secret values are written to the local file only; they are never returned
      to the frontend.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict

from app.core.config import settings

# The ONLY keys the web UI may mirror into .env.
ALLOWED_ENV_KEYS = {
    "OLLAMA_BASE_URL", "OLLAMA_DEFAULT_MODEL",
    "OPENAI_API_KEY", "OPENAI_DEFAULT_MODEL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_DEFAULT_MODEL",
    "GEMINI_API_KEY", "GEMINI_DEFAULT_MODEL",
    "GROK_API_KEY", "GROK_DEFAULT_MODEL",
    "BLACKBOX_API_KEY", "BLACKBOX_DEFAULT_MODEL",
    "CURSOR_API_KEY", "CURSOR_DEFAULT_MODEL", "CURSOR_BASE_URL",
    "DEEPSEEK_API_KEY", "DEEPSEEK_DEFAULT_MODEL",
    "QWEN_API_KEY", "QWEN_DEFAULT_MODEL",
    "OPENROUTER_1_API_KEY", "OPENROUTER_1_DEFAULT_MODEL",
    "OPENROUTER_2_API_KEY", "OPENROUTER_2_DEFAULT_MODEL",
    "OPENROUTER_3_API_KEY", "OPENROUTER_3_DEFAULT_MODEL",
    "OPENROUTER_4_API_KEY", "OPENROUTER_4_DEFAULT_MODEL",
    "OPENROUTER_5_API_KEY", "OPENROUTER_5_DEFAULT_MODEL",
    "OPENROUTER_6_API_KEY", "OPENROUTER_6_DEFAULT_MODEL",
    "N8N_BASE_URL", "N8N_API_KEY",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET", "GOOGLE_CALENDAR_REDIRECT_URI",
    "WEATHER_API_KEY", "WEATHER_PROVIDER",
    "DRIVE_STORAGE_PROVIDER",
    "AI_DEFAULT_PROVIDER", "AI_ALLOW_EXTERNAL_PROVIDERS", "AI_DEFAULT_PRIVACY_MODE",
}


def _format_value(value: str) -> str:
    value = "" if value is None else str(value)
    if value == "" or any(c.isspace() for c in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def sync_env(updates: Dict[str, str]) -> dict:
    """Mirror allowed keys to .env. Returns an env_sync status dict (safe to show)."""
    if not settings.is_local_env:
        return {
            "status": "skipped",
            "message": "Runtime uses database settings. .env mirror skipped (not in local mode).",
            "keys": [],
            "backup": None,
        }

    allowed = {k: v for k, v in (updates or {}).items() if k in ALLOWED_ENV_KEYS}
    if not allowed:
        return {
            "status": "skipped",
            "message": "Saved to the database. No .env-syncable keys in this change.",
            "keys": [],
            "backup": None,
        }

    try:
        path = Path(settings.env_file_path)
        existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

        out: list[str] = []
        seen: set[str] = set()
        for line in existing:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                if key in allowed:
                    out.append(f"{key}={_format_value(allowed[key])}")
                    seen.add(key)
                    continue
            out.append(line)
        for key, value in allowed.items():
            if key not in seen:
                out.append(f"{key}={_format_value(value)}")

        backup_name = None
        if path.exists():
            backup_path = f"{path}.bak.{int(time.time())}"
            shutil.copy2(path, backup_path)
            backup_name = os.path.basename(backup_path)

        tmp = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex}")
        tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

        return {
            "status": "success",
            "message": "Runtime uses database settings immediately. .env mirror updated for local persistence.",
            "keys": sorted(allowed.keys()),
            "backup": backup_name,
        }
    except Exception as exc:  # noqa: BLE001 - DB save already succeeded; surface a safe warning
        return {
            "status": "failed",
            "message": f"Saved to the database, but the .env mirror could not be written: {str(exc)[:160]}",
            "keys": [],
            "backup": None,
        }


# --- key mapping ----------------------------------------------------------

_AI_PREFIX = {
    "openai": "OPENAI", "anthropic": "ANTHROPIC", "gemini": "GEMINI",
    "grok": "GROK", "blackbox": "BLACKBOX",
    "cursor": "CURSOR",
    "deepseek": "DEEPSEEK", "qwen": "QWEN",
    "openrouter_1": "OPENROUTER_1", "openrouter_2": "OPENROUTER_2", "openrouter_3": "OPENROUTER_3",
    "openrouter_4": "OPENROUTER_4", "openrouter_5": "OPENROUTER_5", "openrouter_6": "OPENROUTER_6",
}


def map_ai_provider_updates(provider_id: str, public: dict, secrets: dict) -> Dict[str, str]:
    """Map a saved AI provider's fields to their .env keys (allowed keys only)."""
    out: Dict[str, str] = {}
    if provider_id == "ollama":
        if "base_url" in public:
            out["OLLAMA_BASE_URL"] = public.get("base_url", "")
        if "default_model" in public:
            out["OLLAMA_DEFAULT_MODEL"] = public.get("default_model", "")
        return out
    prefix = _AI_PREFIX.get(provider_id)
    if not prefix:
        return out
    if "api_key" in secrets:
        out[f"{prefix}_API_KEY"] = secrets.get("api_key", "")
    if "default_model" in public:
        out[f"{prefix}_DEFAULT_MODEL"] = public.get("default_model", "")
    if provider_id == "cursor" and "base_url" in public:
        out["CURSOR_BASE_URL"] = public.get("base_url", "")
    return out


_INTEGRATION_MAP = {
    "n8n": {"base_url": "N8N_BASE_URL", "api_key": "N8N_API_KEY"},
    "supabase": {
        "url": "SUPABASE_URL",
        "anon_key": "SUPABASE_ANON_KEY",
        "service_role_key": "SUPABASE_SERVICE_ROLE_KEY",
    },
    "google_calendar": {
        "client_id": "GOOGLE_CALENDAR_CLIENT_ID",
        "client_secret": "GOOGLE_CALENDAR_CLIENT_SECRET",
        "redirect_uri": "GOOGLE_CALENDAR_REDIRECT_URI",
    },
    "drive_storage": {"provider": "DRIVE_STORAGE_PROVIDER"},
    "ollama": {"base_url": "OLLAMA_BASE_URL", "default_model": "OLLAMA_DEFAULT_MODEL"},
}


def map_integration_updates(provider_id: str, public: dict, secrets: dict) -> Dict[str, str]:
    """Map a saved integration's fields to their .env keys (allowed keys only)."""
    mapping = _INTEGRATION_MAP.get(provider_id, {})
    out: Dict[str, str] = {}
    merged = {**(public or {}), **(secrets or {})}
    for field, env_key in mapping.items():
        if field in merged:
            out[env_key] = merged.get(field, "")
    return out
