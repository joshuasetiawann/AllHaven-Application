"""AI Knowledge ingestion/search and related AI workspace plumbing."""

import uuid

from app.core.principal import Principal
from app.domain.ai import AiToolCall
from app.services import ai_tools_registry
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def test_ai_knowledge_upload_indexes_txt_and_searches(auth_client):
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("allhaven.txt", b"AllHaven is a private AI workspace created for desktop-first users.", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"
    assert doc["chunk_count"] >= 1

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "private AI workspace"})
    assert search.status_code == 200, search.text
    results = search.json()["data"]["results"]
    assert results
    assert "private AI workspace" in results[0]["content"]


def test_ai_knowledge_stores_unsupported_file_as_metadata_only(auth_client):
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("source.bin", b"\x00\x01", "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "uploaded"
    assert doc["chunk_count"] == 1
    assert doc["meta"]["metadata_only"] is True
    assert doc["meta"]["indexable"] is False
    assert doc["error_message"]

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "source.bin"})
    assert search.status_code == 200, search.text
    results = search.json()["data"]["results"]
    assert results
    assert results[0]["document_filename"] == "source.bin"


def test_ai_knowledge_protects_secret_like_text_as_metadata_only(auth_client):
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("secrets.env", b"OPENAI_API_KEY=sk-abc123DEF456ghi789", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "uploaded"
    assert doc["chunk_count"] == 1
    assert doc["meta"]["metadata_only"] is True
    assert "Secret-like content" in doc["error_message"]

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "OPENAI_API_KEY"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"] == []


def test_drive_config_exposes_higher_upload_limit(auth_client):
    resp = auth_client.get(f"{API}/drive/config")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["max_upload_mb"] >= 100
    assert data["max_upload_bytes"] == data["max_upload_mb"] * 1024 * 1024


def test_tool_calls_are_logged_to_ai_tool_calls(auth_client, db_session):
    principal = _principal(auth_client)
    outcome = ai_tools_registry.run_tool_call(db_session, principal, "get_current_time", {})
    db_session.commit()
    assert outcome["status"] == "executed"
    row = db_session.query(AiToolCall).filter_by(tool_name="get_current_time").one()
    assert row.status == "executed"
    assert row.access == "read"


def test_school_memory_is_auto_extracted_from_chat(auth_client):
    resp = auth_client.post(f"{API}/ai/chat", json={"message": "saya sekolah di Tzu Chi."})
    assert resp.status_code == 200, resp.text
    memories = auth_client.get(f"{API}/ai/memory/search", params={"q": "Tzu Chi"}).json()["data"]
    assert any("Tzu Chi" in m["content"] for m in memories)
