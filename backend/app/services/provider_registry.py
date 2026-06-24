"""Static registry of integrations and AI providers.

Defines, for each provider, the configurable fields and which are secrets. This
is the single source of truth shared by the config services, routers, and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    secret: bool = False
    required: bool = False
    placeholder: str = ""
    default: str = ""


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    provider_type: str
    purpose: str
    fields: tuple[FieldSpec, ...] = ()
    editable: bool = True
    api_key_required: bool = False
    external: bool = False  # AI providers: external network call (vs local)
    default_model: str = ""

    def secret_fields(self) -> list[str]:
        return [f.key for f in self.fields if f.secret]

    def public_fields(self) -> list[str]:
        return [f.key for f in self.fields if not f.secret]

    def required_fields(self) -> list[str]:
        return [f.key for f in self.fields if f.required]


# --- Tool / infrastructure integrations -----------------------------------

INTEGRATIONS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="postgresql",
        name="PostgreSQL",
        provider_type="system",
        purpose="Primary relational database",
        editable=False,
    ),
    ProviderSpec(
        id="ollama",
        name="Ollama Local AI",
        provider_type="local_ai",
        purpose="Local LLM inference (desktop-local; reach from mobile via Desktop Bridge)",
        fields=(
            FieldSpec("base_url", "Local URL", required=True, placeholder="http://localhost:11434"),
            FieldSpec("default_model", "Default model", placeholder="llama3.1"),
            # --- Desktop Bridge (v4.0) ---
            FieldSpec("connection_mode", "Connection mode", placeholder="local_desktop", default="local_desktop"),
            FieldSpec("tailscale_url", "Tailscale Private URL", placeholder="http://100.x.y.z:11434"),
            FieldSpec("serve_url", "Tailscale Serve URL", placeholder="https://desktop.tailnet.ts.net/ollama"),
            FieldSpec("funnel_url", "Tailscale Funnel URL (public)", placeholder="https://...ts.net (disabled by default)"),
            FieldSpec("funnel_enabled", "Funnel enabled", placeholder="false", default="false"),
        ),
    ),
    ProviderSpec(
        id="n8n",
        name="n8n Automation",
        provider_type="automation",
        purpose="Workflow automation (desktop-local; reach from mobile via Desktop Bridge)",
        fields=(
            FieldSpec("base_url", "Local URL", required=True, placeholder="http://localhost:5678"),
            FieldSpec("api_key", "API key (optional)", secret=True),
            # --- Desktop Bridge (v4.0) ---
            FieldSpec("connection_mode", "Connection mode", placeholder="local_desktop", default="local_desktop"),
            FieldSpec("tailscale_url", "Tailscale Private URL", placeholder="http://100.x.y.z:5678"),
            FieldSpec("serve_url", "Tailscale Serve URL", placeholder="https://desktop.tailnet.ts.net/n8n"),
            FieldSpec("funnel_url", "Tailscale Funnel URL (public)", placeholder="https://...ts.net (disabled by default)"),
            FieldSpec("funnel_enabled", "Funnel enabled", placeholder="false", default="false"),
        ),
    ),
    ProviderSpec(
        id="supabase",
        name="Supabase",
        provider_type="auth_storage",
        purpose="Auth, storage, realtime",
        fields=(
            FieldSpec("url", "Project URL", required=True, placeholder="https://xxxx.supabase.co"),
            FieldSpec("anon_key", "Anon key", required=True),
            FieldSpec("service_role_key", "Service role key (server-side only)", secret=True),
        ),
    ),
    ProviderSpec(
        id="google_calendar",
        name="Google Calendar",
        provider_type="calendar",
        purpose="Calendar and schedule sync",
        fields=(
            FieldSpec("client_id", "Client ID", required=True),
            FieldSpec("redirect_uri", "Redirect URI", required=True, placeholder="http://localhost:3000/oauth/callback"),
            FieldSpec("client_secret", "Client secret (server-side only)", secret=True),
        ),
    ),
    ProviderSpec(
        id="drive_storage",
        name="Drive Storage",
        provider_type="storage",
        purpose="File storage (local or Supabase)",
        fields=(
            FieldSpec("provider", "Provider", placeholder="local", default="local"),
            FieldSpec("bucket", "Bucket / folder (optional)", placeholder="allhaven-files"),
        ),
    ),
    ProviderSpec(
        id="google",
        name="Google OAuth",
        provider_type="auth_provider",
        purpose="Google login & scoped API access",
        fields=(
            FieldSpec("client_id", "Client ID", required=True, placeholder="…apps.googleusercontent.com"),
            FieldSpec(
                "redirect_uri",
                "Redirect URI",
                required=True,
                placeholder="http://localhost:3000/oauth/google/callback",
            ),
            FieldSpec("client_secret", "Client secret (server-side only)", secret=True, required=True),
        ),
    ),
)


# --- AI agent providers ----------------------------------------------------

AI_PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="ollama",
        name="Ollama Local Agent",
        provider_type="local",
        purpose="Local, private LLM inference",
        external=False,
        api_key_required=False,
        fields=(
            FieldSpec("base_url", "Base URL", required=True, placeholder="http://localhost:11434"),
            FieldSpec("default_model", "Default model", placeholder="llama3.1"),
        ),
    ),
    ProviderSpec(
        id="openai",
        name="GPT Agent",
        provider_type="api_key",
        purpose="OpenAI / GPT models",
        external=True,
        api_key_required=True,
        default_model="gpt-4.1-mini",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-…"),
            FieldSpec("default_model", "Default model", placeholder="gpt-4.1-mini"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://api.openai.com/v1"),
        ),
    ),
    ProviderSpec(
        id="anthropic",
        name="Claude Agent",
        provider_type="api_key",
        purpose="Anthropic Claude models",
        external=True,
        api_key_required=True,
        default_model="claude-sonnet-4-5",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-ant-…"),
            FieldSpec("default_model", "Default model", placeholder="claude-sonnet-4-5"),
        ),
    ),
    ProviderSpec(
        id="gemini",
        name="Gemini Agent",
        provider_type="api_key",
        purpose="Google Gemini models",
        external=True,
        api_key_required=True,
        default_model="gemini-1.5-flash",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True),
            FieldSpec("default_model", "Default model", placeholder="gemini-1.5-flash"),
        ),
    ),
    ProviderSpec(
        id="grok",
        name="Grok / xAI Agent",
        provider_type="api_key",
        purpose="xAI Grok models",
        external=True,
        api_key_required=True,
        default_model="grok-2-latest",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True),
            FieldSpec("default_model", "Default model", placeholder="grok-2-latest"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://api.x.ai/v1"),
        ),
    ),
    ProviderSpec(
        id="blackbox",
        name="Blackbox Agent",
        provider_type="api_key",
        purpose="Blackbox AI models",
        external=True,
        api_key_required=True,
        default_model="blackbox-default",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True),
            FieldSpec("default_model", "Default model", placeholder="blackbox-default"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://api.blackbox.ai/v1"),
        ),
    ),
    ProviderSpec(
        id="cursor",
        name="Cursor AI Agent",
        provider_type="api_key",
        purpose="Cursor/OpenAI-compatible coding gateway for chat agents",
        external=True,
        api_key_required=True,
        default_model="",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True),
            FieldSpec("default_model", "Default model", placeholder="cursor-agent or gateway model name"),
            FieldSpec(
                "base_url",
                "Base URL",
                required=True,
                placeholder="https://your-openai-compatible-gateway/v1",
            ),
        ),
    ),
    ProviderSpec(
        id="deepseek",
        name="DeepSeek Agent",
        provider_type="api_key",
        purpose="DeepSeek chat, coding, and reasoning models",
        external=True,
        api_key_required=True,
        default_model="deepseek-chat",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True),
            FieldSpec("default_model", "Default model", placeholder="deepseek-chat"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://api.deepseek.com/v1"),
        ),
    ),
    ProviderSpec(
        id="qwen",
        name="Qwen Agent",
        provider_type="api_key",
        purpose="Alibaba Qwen / DashScope OpenAI-compatible models",
        external=True,
        api_key_required=True,
        default_model="qwen-plus",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True),
            FieldSpec("default_model", "Default model", placeholder="qwen-plus"),
            FieldSpec(
                "base_url",
                "Base URL (optional)",
                placeholder="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
        ),
    ),
    # Six independent OpenRouter agents, each with its own key + default model,
    # so users can run several OpenRouter-backed models side by side. Defaults are
    # LIGHT models. Free models exist on OpenRouter (look for the ":free" suffix at
    # openrouter.ai/models) — they rotate, so set the current one in the UI.
    # Base URL is overridable for OpenRouter-compatible gateways/proxies.
    ProviderSpec(
        id="openrouter_1",
        name="OpenRouter Agent 1",
        provider_type="api_key",
        purpose="OpenRouter model marketplace (slot 1)",
        external=True,
        api_key_required=True,
        default_model="openai/gpt-4o-mini",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-or-…"),
            FieldSpec("default_model", "Default model (light)", placeholder="openai/gpt-4o-mini"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://openrouter.ai/api/v1"),
        ),
    ),
    ProviderSpec(
        id="openrouter_2",
        name="OpenRouter Agent 2",
        provider_type="api_key",
        purpose="OpenRouter model marketplace (slot 2)",
        external=True,
        api_key_required=True,
        default_model="meta-llama/llama-3.1-8b-instruct",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-or-…"),
            FieldSpec("default_model", "Default model (light)", placeholder="meta-llama/llama-3.1-8b-instruct"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://openrouter.ai/api/v1"),
        ),
    ),
    ProviderSpec(
        id="openrouter_3",
        name="OpenRouter Agent 3",
        provider_type="api_key",
        purpose="OpenRouter model marketplace (slot 3)",
        external=True,
        api_key_required=True,
        default_model="google/gemini-2.0-flash-001",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-or-…"),
            FieldSpec("default_model", "Default model (light)", placeholder="google/gemini-2.0-flash-001"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://openrouter.ai/api/v1"),
        ),
    ),
    ProviderSpec(
        id="openrouter_4",
        name="OpenRouter Agent 4",
        provider_type="api_key",
        purpose="OpenRouter model marketplace (slot 4)",
        external=True,
        api_key_required=True,
        default_model="",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-or-…"),
            FieldSpec("default_model", "Default model", placeholder="e.g. anthropic/claude-3.5-haiku"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://openrouter.ai/api/v1"),
        ),
    ),
    ProviderSpec(
        id="openrouter_5",
        name="OpenRouter Agent 5",
        provider_type="api_key",
        purpose="OpenRouter model marketplace (slot 5)",
        external=True,
        api_key_required=True,
        default_model="",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-or-…"),
            FieldSpec("default_model", "Default model", placeholder="e.g. deepseek/deepseek-chat"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://openrouter.ai/api/v1"),
        ),
    ),
    ProviderSpec(
        id="openrouter_6",
        name="OpenRouter Agent 6",
        provider_type="api_key",
        purpose="OpenRouter model marketplace (slot 6)",
        external=True,
        api_key_required=True,
        default_model="",
        fields=(
            FieldSpec("api_key", "API key", secret=True, required=True, placeholder="sk-or-…"),
            FieldSpec("default_model", "Default model", placeholder="e.g. qwen/qwen-2.5-72b-instruct"),
            FieldSpec("base_url", "Base URL (optional)", placeholder="https://openrouter.ai/api/v1"),
        ),
    ),
)

# AI providers that share an adapter class with a base provider id (e.g. the six
# OpenRouter slots all use the OpenRouter adapter).
ADAPTER_ALIASES = {
    "openrouter_1": "openrouter",
    "openrouter_2": "openrouter",
    "openrouter_3": "openrouter",
    "openrouter_4": "openrouter",
    "openrouter_5": "openrouter",
    "openrouter_6": "openrouter",
}

_INTEGRATIONS_BY_ID = {p.id: p for p in INTEGRATIONS}
_AI_PROVIDERS_BY_ID = {p.id: p for p in AI_PROVIDERS}


def get_integration_spec(provider_id: str) -> Optional[ProviderSpec]:
    return _INTEGRATIONS_BY_ID.get(provider_id)


def get_ai_provider_spec(provider_id: str) -> Optional[ProviderSpec]:
    return _AI_PROVIDERS_BY_ID.get(provider_id)
