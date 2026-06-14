"""LLM service boundary.

The MVP does NOT perform live LLM generation. If Ollama is not configured, the
assistant returns an honest "not configured" reply. If a base URL is configured,
it still returns an honest "live generation is disabled in this MVP" reply rather
than faking output. This keeps the integration policy intact: no fake success.
"""

from __future__ import annotations

from typing import List

from app.core.config import settings
from app.services.integration_status_service import is_configured_value

NOT_CONFIGURED_MESSAGE = (
    "The AI assistant is not configured yet. Set OLLAMA_BASE_URL to a running "
    "Ollama server to enable local AI. AllHaven will never fake AI responses, and "
    "any AI suggestion will require your explicit approval before it can act."
)

CONFIGURED_BUT_DISABLED_MESSAGE = (
    "An AI endpoint is configured, but live generation is intentionally disabled "
    "in this MVP build. Your message has been saved. When enabled, the assistant "
    "will only ever propose actions for your approval — it cannot execute writes."
)


class LLMService:
    """Thin, replaceable boundary around the (future) local LLM."""

    def is_configured(self) -> bool:
        return is_configured_value(settings.OLLAMA_BASE_URL)

    def generate_reply(self, messages: List[dict]) -> dict:
        """Return an honest assistant reply. Never fabricates model output."""
        if not self.is_configured():
            return {
                "content": NOT_CONFIGURED_MESSAGE,
                "configured": False,
                "meta": {"source": "system", "reason": "ollama_not_configured"},
            }
        return {
            "content": CONFIGURED_BUT_DISABLED_MESSAGE,
            "configured": True,
            "meta": {"source": "system", "reason": "live_generation_disabled_in_mvp"},
        }


llm_service = LLMService()
