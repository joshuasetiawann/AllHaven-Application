"""v4.0 Desktop Bridge tests: connection resolution by mode, honest Ollama/n8n
gating (online only if the resolved endpoint responds), Funnel disabled by default,
and API-key AI providers staying independent of the bridge."""
from app.services import integration_config_service as ics
from app.services.connection_resolver import DEFAULT_MODE, funnel_enabled, resolve
from app.services.provider_registry import get_integration_spec

OLLAMA_URLS = {
    "base_url": "http://localhost:11434",
    "tailscale_url": "http://100.1.2.3:11434",
    "serve_url": "https://desktop.tailnet.ts.net/ollama",
    "funnel_url": "https://public.ts.net/ollama",
}


def test_resolver_picks_url_by_mode():
    assert resolve({**OLLAMA_URLS, "connection_mode": "local_desktop"})[0] == "http://localhost:11434"
    assert resolve({**OLLAMA_URLS, "connection_mode": "tailscale_private"})[0] == "http://100.1.2.3:11434"
    assert resolve({**OLLAMA_URLS, "connection_mode": "tailscale_serve"})[0] == "https://desktop.tailnet.ts.net/ollama"


def test_default_mode_is_local():
    url, mode, _ = resolve(OLLAMA_URLS)  # no connection_mode
    assert mode == DEFAULT_MODE and url == "http://localhost:11434"


def test_funnel_disabled_by_default():
    assert funnel_enabled(OLLAMA_URLS) is False
    url, mode, reason = resolve({**OLLAMA_URLS, "connection_mode": "tailscale_funnel"})
    assert url is None and mode == "tailscale_funnel" and "Funnel" in reason


def test_funnel_requires_explicit_enable():
    url, _, _ = resolve({**OLLAMA_URLS, "connection_mode": "tailscale_funnel", "funnel_enabled": "true"})
    assert url == "https://public.ts.net/ollama"


def test_auto_never_uses_funnel_and_prefers_local():
    cfg = {"connection_mode": "auto", "funnel_url": "https://public.ts.net/ollama", "funnel_enabled": "true",
           "serve_url": "https://serve.ts.net/ollama"}
    url, mode, _ = resolve(cfg)
    assert mode == "tailscale_serve" and url == "https://serve.ts.net/ollama"  # serve preferred over funnel
    url2, _, _ = resolve({**cfg, "base_url": "http://localhost:11434"})
    assert url2 == "http://localhost:11434"  # local wins in auto


def test_no_url_for_mode_is_not_configured():
    url, mode, reason = resolve({"connection_mode": "tailscale_private"})  # no tailscale_url
    assert url is None and reason


# --- honest verify gating (online only if resolved endpoint responds) -------- #

def test_ollama_unreachable_endpoint_is_not_online():
    spec = get_integration_spec("ollama")
    # A resolved URL that nothing listens on → must NOT be online.
    status, _ = ics._verify(None, spec, {"connection_mode": "local_desktop", "base_url": "http://127.0.0.1:1"}, {})
    assert status != "online"


def test_ollama_no_endpoint_is_not_configured():
    spec = get_integration_spec("ollama")
    status, _ = ics._verify(None, spec, {"connection_mode": "tailscale_private"}, {})
    assert status == "not_configured"


def test_n8n_unreachable_endpoint_is_not_online():
    spec = get_integration_spec("n8n")
    status, _ = ics._verify(None, spec, {"connection_mode": "local_desktop", "base_url": "http://127.0.0.1:1"}, {})
    assert status != "online"


# --- API-key AI providers stay independent of the bridge --------------------- #

def test_api_providers_do_not_use_bridge_resolver():
    """AI-key providers (openai, claude, ...) must NOT be gated by Tailscale/bridge:
    the bridge resolver is only wired into the ollama/n8n integration verify paths."""
    import inspect

    from app.services import ai_provider_router

    src = inspect.getsource(ai_provider_router)
    assert "connection_resolver" not in src and "resolve(" not in src
