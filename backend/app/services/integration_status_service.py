"""Integration status service.

Reports honest configuration status for each integration based on environment
variables. It never exposes secret values and never reports an integration as
"connected" unless it can actually be verified (only PostgreSQL is live-checked).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

# Values that indicate a placeholder rather than a real configuration.
_PLACEHOLDER_HINTS = (
    "changeme", "change-me", "placeholder", "example", "your-", "your_",
    "xxx", "todo", "<", "...",
)
_PLACEHOLDER_EXACT = {
    "", "none", "null", "disabled", "test", "sk-test", "your-api-key",
    "your_api_key", "api-key", "api_key", "apikey", "key", "secret",
}


def is_configured_value(value: Optional[str]) -> bool:
    """Return True only if a value looks like a real (non-placeholder) setting.

    This only filters *obvious* placeholders so they stay ``not_configured``. It is
    NOT a substitute for verification — a non-placeholder value is treated as
    ``configured``, never ``online`` (that requires a successful Test Connection).
    """
    if not value:
        return False
    normalized = value.strip().lower()
    if normalized in _PLACEHOLDER_EXACT:
        return False
    return not any(hint in normalized for hint in _PLACEHOLDER_HINTS)


def _status(configured: bool) -> str:
    return "configured" if configured else "not_configured"


def get_integration_status(db: Session) -> list[dict]:
    """Build the integration status list. Secrets are never included."""
    integrations: list[dict] = []

    # PostgreSQL — live-checked.
    try:
        db.execute(text("SELECT 1"))
        integrations.append(
            {
                "key": "postgresql",
                "name": "PostgreSQL",
                "status": "connected",
                "configured": True,
                "detail": "Connected",
            }
        )
    except Exception:
        integrations.append(
            {
                "key": "postgresql",
                "name": "PostgreSQL",
                "status": "error",
                "configured": True,
                "detail": "Database is configured but not reachable",
            }
        )

    # Ollama — configured if a real base URL is set (not live-pinged in MVP).
    ollama = is_configured_value(settings.OLLAMA_BASE_URL)
    integrations.append(
        {
            "key": "ollama",
            "name": "Ollama (Local AI)",
            "status": _status(ollama),
            "configured": ollama,
            "detail": "Configured (live calls disabled in MVP)" if ollama else "Not configured",
        }
    )

    # n8n.
    n8n = is_configured_value(settings.N8N_BASE_URL)
    integrations.append(
        {
            "key": "n8n",
            "name": "n8n Automations",
            "status": _status(n8n),
            "configured": n8n,
            "detail": "Configured" if n8n else "Not configured",
        }
    )

    # Supabase — needs both URL and anon key.
    supabase = is_configured_value(settings.SUPABASE_URL) and is_configured_value(
        settings.SUPABASE_ANON_KEY
    )
    integrations.append(
        {
            "key": "supabase",
            "name": "Supabase",
            "status": _status(supabase),
            "configured": supabase,
            "detail": "Configured" if supabase else "Not configured",
        }
    )

    # Google Calendar.
    calendar = is_configured_value(settings.GOOGLE_CALENDAR_CLIENT_ID)
    integrations.append(
        {
            "key": "google_calendar",
            "name": "Google Calendar",
            "status": _status(calendar),
            "configured": calendar,
            "detail": "Configured" if calendar else "Not configured",
        }
    )

    return integrations
