"""Tests for image (vision) support in chat: data-URL parsing, provider payload
formatting, and that an attached image reaches the provider and is persisted."""

from tests.conftest import API

import app.services.ai_providers.base as base
from app.services.ai_providers.base import openai_message_content, parse_data_url

# A valid 1x1 PNG as a data URL.
DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAA"
    "C0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def test_parse_data_url():
    media, b64 = parse_data_url(DATA_URL)
    assert media == "image/png"
    assert b64.startswith("iVBOR")
    assert parse_data_url("https://example.com/x.png") == ("", "https://example.com/x.png")


def test_openai_message_content_with_image():
    content = openai_message_content({"content": "hello", "images": [DATA_URL]})
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "hello"}
    assert content[1]["type"] == "image_url" and content[1]["image_url"]["url"] == DATA_URL


def test_openai_message_content_text_only_stays_string():
    assert openai_message_content({"content": "hi", "images": []}) == "hi"


def test_multi_chat_sends_image_to_provider_and_persists(auth_client, monkeypatch):
    auth_client.put(f"{API}/ai/policy", json={"allow_external": True})
    auth_client.put(f"{API}/ai/providers/openai", json={"secrets": {"api_key": "sk-x"}, "enabled": True})

    captured: dict = {}

    def fake_request(method, url, **kw):
        captured["json"] = kw.get("json")
        return (200, {"choices": [{"message": {"content": "It is a 1x1 pixel."}}]}, "")

    monkeypatch.setattr(base, "safe_request", fake_request)

    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "what is this?", "provider_ids": ["openai"], "images": [DATA_URL]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["agent_responses"][0]["status"] == "completed"

    # The provider received the image as an image_url content part.
    user_payload = captured["json"]["messages"][-1]
    assert isinstance(user_payload["content"], list)
    assert any(p.get("type") == "image_url" for p in user_payload["content"])

    # The user's message persisted with its attached image (shows on reload).
    stored = auth_client.get(f"{API}/ai/sessions/{data['session_id']}/messages").json()["data"]
    user_msg = next(m for m in stored if m["role"] == "user")
    assert (user_msg.get("meta") or {}).get("images") == [DATA_URL]


def test_more_than_four_images_rejected(auth_client):
    resp = auth_client.post(
        f"{API}/ai/chat/multi",
        json={"message": "hi", "provider_ids": ["ollama"], "images": [DATA_URL] * 5},
    )
    assert resp.status_code == 422, resp.text
