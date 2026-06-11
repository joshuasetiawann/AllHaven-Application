"""Tests for the v0.5.0 upgrade: Thinking Mode, provider capabilities, image
routing to vision-only providers, and the calculator evaluator."""

import pytest

from tests.conftest import API

import app.services.ai_providers.base as base
from app.services.ai_multi_service import _is_image_unsupported
from app.services.calc_service import CalcError, evaluate
from app.services.thinking import reasoning_depth, thinking_params

DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAA"
    "C0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


# --- Thinking Mode --------------------------------------------------------

def test_thinking_params_table():
    # Default (balance) leans warmer for natural, human-sounding prose; thinking/deep
    # stay low so analytical and grounded work remains careful.
    assert thinking_params("fast") == {"temperature": 0.45, "top_p": 0.90}
    assert thinking_params("balance") == {"temperature": 0.40, "top_p": 0.85}
    assert thinking_params("thinking") == {"temperature": 0.20, "top_p": 0.75}
    assert thinking_params("deep") == {"temperature": 0.10, "top_p": 0.70}
    assert thinking_params("nonsense") == thinking_params("balance")  # default


def test_reasoning_depth_mapping():
    assert reasoning_depth("fast") == "fast"
    assert reasoning_depth("balance") == "balanced"
    assert reasoning_depth("thinking") == "deep"
    assert reasoning_depth("deep") == "deep"


# --- Calculator -----------------------------------------------------------

def test_calculator_basic_ops():
    assert evaluate("2+2") == 4
    assert evaluate("10 - 3") == 7
    assert evaluate("6*7") == 42
    assert evaluate("9 / 2") == 4.5
    assert evaluate("10 % 3") == 1
    assert evaluate("-(3 + 4) * 2") == -14
    assert evaluate("2 + 3 * 4") == 14  # operator precedence


@pytest.mark.parametrize("bad", ["__import__('os')", "a + 1", "2 ** 9999", "", "1/0"])
def test_calculator_rejects_unsafe(bad):
    with pytest.raises(CalcError):
        evaluate(bad)


# --- Provider capabilities ------------------------------------------------

def test_provider_list_exposes_capabilities(auth_client):
    providers = auth_client.get(f"{API}/ai/providers").json()["data"]["providers"]
    by_id = {p["id"]: p for p in providers}
    assert by_id["openai"]["capabilities"] == {"text": True, "image": True, "tools": True}
    assert by_id["ollama"]["capabilities"]["image"] is True
    assert by_id["blackbox"]["capabilities"]["image"] is False


# --- Image routed only to vision-capable providers ------------------------

def test_image_to_non_vision_provider_is_unsupported(auth_client):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    auth_client.put(f"{API}/ai/providers/blackbox", json={"secrets": {"api_key": "sk-x"}, "enabled": True})
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "what is this?", "provider_ids": ["blackbox"], "images": [DATA_URL]},
    )
    assert resp.status_code == 200, resp.text
    agent = resp.json()["data"]["agent_responses"][0]
    assert agent["status"] == "unsupported"


# --- Thinking mode changes the generation settings sent to the provider ---

def test_thinking_mode_sets_generation_params(auth_client, monkeypatch):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    auth_client.put(f"{API}/ai/providers/openai", json={"secrets": {"api_key": "sk-x"}, "enabled": True})
    captured: dict = {}

    def fake(method, url, **kw):
        captured["json"] = kw.get("json")
        return (200, {"choices": [{"message": {"content": "ok"}}]}, "")

    monkeypatch.setattr(base, "safe_request", fake)
    auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "hi", "provider_ids": ["openai"], "thinking_mode": "deep"},
    )
    assert captured["json"]["temperature"] == 0.1
    assert captured["json"]["top_p"] == 0.7


# --- Vision-capable provider but text-only model -> honest 'unsupported' ---

def test_is_image_unsupported_detects_provider_errors():
    assert _is_image_unsupported("Multimodal data provided, but model does not support multimodal requests.")
    assert _is_image_unsupported("No endpoints found that support image input")
    assert not _is_image_unsupported("the provider rate-limited the request (HTTP 429).")


def test_image_to_text_only_model_is_reclassified_unsupported(auth_client, monkeypatch):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    auth_client.put(f"{API}/ai/providers/openai", json={"secrets": {"api_key": "sk-x"}, "enabled": True})

    def fake(method, url, **kw):
        # A vision-capable provider, but the chosen model rejects images.
        return (400, {"error": {"message": "Multimodal data provided, but model does not support multimodal requests."}}, "")

    monkeypatch.setattr(base, "safe_request", fake)
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "what is this?", "provider_ids": ["openai"], "images": [DATA_URL]},
    )
    assert resp.status_code == 200, resp.text
    agent = resp.json()["data"]["agent_responses"][0]
    assert agent["status"] == "unsupported"
    assert "vision model" in (agent["error_message"] or "").lower()
