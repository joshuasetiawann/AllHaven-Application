"""Blackbox AI provider adapter (OpenAI-compatible chat API).

Blackbox does not expose a documented, authenticated verification endpoint we can
rely on. To stay honest, test_connection NEVER reports "online" — it reports
"configured" (saved but not verified). Chat still works if the key/endpoint are
valid; failures are surfaced honestly.
"""

from __future__ import annotations

from app.services.ai_providers.base import OpenAICompatibleProvider, VerifyResult


class BlackboxProvider(OpenAICompatibleProvider):
    id = "blackbox"
    name = "Blackbox Agent"
    external = True
    requires_api_key = True
    default_base_url = "https://api.blackbox.ai/v1"
    default_model = "blackbox-default"

    def test_connection(self, public: dict, secrets: dict) -> VerifyResult:
        if not secrets.get("api_key"):
            return VerifyResult("not_configured", "API key not set")
        return VerifyResult(
            "configured",
            "Saved. Automated verification is not available for Blackbox, so it is marked "
            "configured (not verified) rather than online.",
        )
