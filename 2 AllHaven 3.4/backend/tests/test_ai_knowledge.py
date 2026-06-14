"""AI Knowledge ingestion/search and related AI workspace plumbing."""

import io
import uuid
import zipfile

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


def test_ai_knowledge_upload_indexes_simple_pdf(auth_client):
    pdf = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Contents 4 0 R>> endobj
4 0 obj <</Length 64>> stream
BT /F1 12 Tf 72 720 Td (AllHaven PDF routine finance knowledge) Tj ET
endstream endobj
trailer <</Root 1 0 R>>
%%EOF
"""
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("planning.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "routine finance knowledge"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"]


def test_ai_knowledge_upload_indexes_docx(auth_client):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>AllHaven DOCX schedule and coding plan</w:t></w:r></w:p></w:body>
            </w:document>
            """,
        )
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={
            "file": (
                "plan.docx",
                data.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "schedule coding plan"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"]


def test_ai_knowledge_rejects_malicious_docx_entity_expansion(auth_client):
    # A DOCX whose document.xml declares a DTD with an entity. defusedxml must
    # refuse the entity instead of expanding it (XXE / billion-laughs), so the
    # upload falls back to safe metadata-only storage rather than crashing.
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<?xml version="1.0"?>
            <!DOCTYPE w:document [
              <!ENTITY xxe SYSTEM "file:///etc/passwd">
              <!ENTITY lol "lololololololololol">
            ]>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body><w:p><w:r><w:t>&xxe;&lol;</w:t></w:r></w:p></w:body>
            </w:document>
            """,
        )
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={
            "file": (
                "evil.docx",
                data.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["meta"]["metadata_only"] is True
    assert doc["meta"]["indexable"] is False
    assert doc["error_message"]


def test_ai_knowledge_upload_indexes_legacy_doc_best_effort(auth_client):
    body = b"\xd0\xcf\x11\xe0" + b"\x00" * 20 + b"AllHaven legacy DOC finance routine readable text"
    resp = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": ("legacy.doc", body, "application/msword")},
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "indexed"

    search = auth_client.get(f"{API}/ai/knowledge/search", params={"q": "legacy finance routine"})
    assert search.status_code == 200, search.text
    assert search.json()["data"]["results"]


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
