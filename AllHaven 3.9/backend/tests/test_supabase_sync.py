"""Tests for app/services/supabase_sync_service.py (Task 16).

Covers:
- _get_credentials: no row → (None, None); disabled row → (None, None); enabled row → (url, key)
- is_enabled: True/False
- sync_all without creds → not_configured, no Thread started
- sync_all with creds → status 'syncing', daemon Thread started with correct args
- _serialize: handles datetimes, UUIDs, None, dict/list, primitive types
- _do_sync: monkeypatched urllib posts to correct URLs with apikey/Prefer headers;
  empty table → no request; body is valid JSON containing seeded row
- Endpoint: POST /ai/memory/sync/supabase returns 'not_configured' (module present)
"""
from __future__ import annotations

import json
import threading
import uuid
from unittest.mock import MagicMock, patch

from app.core.principal import Principal
from app.core.secrets import encrypt_secret
from app.domain.integrations import IntegrationConfig
from app.services import supabase_sync_service
from tests.conftest import API


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_principal(auth_client) -> Principal:
    """Extract a Principal from an already-authenticated TestClient via /auth/me."""
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _insert_integration_row(
    db_session,
    principal: Principal,
    *,
    url: str,
    anon_key: str,
    enabled: bool = True,
) -> IntegrationConfig:
    """Directly insert an IntegrationConfig row the way the service stores it.

    In AllHaven's registry, supabase's ``url`` and ``anon_key`` are public
    (non-secret) fields stored in public_config, not encrypted_secrets.
    """
    row = IntegrationConfig(
        workspace_id=principal.workspace_id,
        provider_id="supabase",
        provider_type="auth_storage",
        display_name="Supabase",
        enabled=enabled,
        status="configured",
        public_config={"url": url, "anon_key": anon_key},
        encrypted_secrets={},
        created_by=principal.user_id,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# _get_credentials
# ---------------------------------------------------------------------------


def test_get_credentials_no_row(auth_client, db_session):
    principal = _make_principal(auth_client)
    url, key = supabase_sync_service._get_credentials(db_session, principal)
    assert url is None
    assert key is None


def test_get_credentials_disabled_row(auth_client, db_session):
    principal = _make_principal(auth_client)
    _insert_integration_row(
        db_session, principal,
        url="https://abc.supabase.co",
        anon_key="test-anon-key",
        enabled=False,
    )
    url, key = supabase_sync_service._get_credentials(db_session, principal)
    assert url is None
    assert key is None


def test_get_credentials_enabled_row(auth_client, db_session):
    principal = _make_principal(auth_client)
    _insert_integration_row(
        db_session, principal,
        url="https://abc.supabase.co",
        anon_key="test-anon-key-123",
        enabled=True,
    )
    url, key = supabase_sync_service._get_credentials(db_session, principal)
    assert url == "https://abc.supabase.co"
    assert key == "test-anon-key-123"


def test_get_credentials_with_encrypted_service_role_key(auth_client, db_session):
    """If only encrypted service_role_key is present (no public anon_key), it is used."""
    principal = _make_principal(auth_client)
    encrypted_key = encrypt_secret("service-role-secret")
    row = IntegrationConfig(
        workspace_id=principal.workspace_id,
        provider_id="supabase",
        provider_type="auth_storage",
        display_name="Supabase",
        enabled=True,
        status="configured",
        public_config={"url": "https://xyz.supabase.co"},
        encrypted_secrets={"service_role_key": encrypted_key},
        created_by=principal.user_id,
    )
    db_session.add(row)
    db_session.commit()

    url, key = supabase_sync_service._get_credentials(db_session, principal)
    assert url == "https://xyz.supabase.co"
    assert key == "service-role-secret"


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------


def test_is_enabled_false_no_row(auth_client, db_session):
    principal = _make_principal(auth_client)
    assert supabase_sync_service.is_enabled(db_session, principal) is False


def test_is_enabled_false_disabled(auth_client, db_session):
    principal = _make_principal(auth_client)
    _insert_integration_row(
        db_session, principal,
        url="https://abc.supabase.co",
        anon_key="key",
        enabled=False,
    )
    assert supabase_sync_service.is_enabled(db_session, principal) is False


def test_is_enabled_true(auth_client, db_session):
    principal = _make_principal(auth_client)
    _insert_integration_row(
        db_session, principal,
        url="https://abc.supabase.co",
        anon_key="real-anon-key",
        enabled=True,
    )
    assert supabase_sync_service.is_enabled(db_session, principal) is True


# ---------------------------------------------------------------------------
# sync_all: not configured (no thread)
# ---------------------------------------------------------------------------


def test_sync_all_not_configured_no_creds(auth_client, db_session):
    principal = _make_principal(auth_client)

    with patch.object(threading.Thread, "start") as mock_start:
        result = supabase_sync_service.sync_all(db_session, principal)

    assert result["status"] == "not_configured"
    assert "Configure" in result["message"]
    mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# sync_all: with creds → syncing + thread started with right args
# ---------------------------------------------------------------------------


def test_sync_all_with_creds_starts_thread(auth_client, db_session):
    principal = _make_principal(auth_client)
    _insert_integration_row(
        db_session, principal,
        url="https://abc.supabase.co",
        anon_key="test-key-xyz",
        enabled=True,
    )

    captured: dict = {}

    class CapturingThread(threading.Thread):
        def __init__(self, target=None, args=(), daemon=None, **kwargs):
            # Record what was passed but don't call super().__init__
            # so the thread body never actually runs in tests.
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon
            # Still need to be a minimal Thread-like object for t.start()
            super().__init__(target=lambda: None, daemon=daemon)

    with patch("threading.Thread", CapturingThread):
        result = supabase_sync_service.sync_all(db_session, principal)

    assert result["status"] == "syncing"
    assert captured["target"] is supabase_sync_service._sync_thread
    assert captured["args"][0] == "https://abc.supabase.co"
    assert captured["args"][1] == "test-key-xyz"
    assert captured["args"][2] == str(principal.workspace_id)
    assert captured["daemon"] is True


# ---------------------------------------------------------------------------
# _serialize (tested via _do_sync with mocked urlopen)
# ---------------------------------------------------------------------------


def test_serialize_primitives_and_none(auth_client, db_session):
    """_serialize on a real ORM row handles primitives, datetime, UUID, and None correctly.

    Uses AiMemory (which has all these types) and calls _do_sync with a mocked urlopen
    to exercise the real _serialize function — not a hand-rolled copy of its loop.
    """
    import datetime as _dt

    from app.domain.ai_memory import AiMemory

    principal = _make_principal(auth_client)

    # Use an explicit last_used_at to exercise datetime → isoformat
    ts = _dt.datetime(2024, 1, 15, 12, 0, 0)
    mem = AiMemory(
        workspace_id=principal.workspace_id,
        category="Profile",
        title="primitives-test",
        content="checking types",
        source="manual",
        sensitivity="LOW",
        confidence=3.14,
        enabled=True,
        last_used_at=ts,
        meta=None,
    )
    db_session.add(mem)
    db_session.commit()
    db_session.refresh(mem)

    captured_bodies: dict[str, list] = {}

    def fake_urlopen(req, timeout=None):
        table = req.get_full_url().split("/rest/v1/")[1]
        captured_bodies[table] = json.loads(req.data.decode())
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        return fake_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        supabase_sync_service._do_sync(
            db_session,
            "https://abc.supabase.co",
            "key",
            str(principal.workspace_id),
        )

    assert "ai_memories" in captured_bodies
    row_data = captured_bodies["ai_memories"][0]

    # id and workspace_id must be str (UUIDs serialised)
    assert isinstance(row_data["id"], str)
    assert isinstance(row_data["workspace_id"], str)
    # datetime field must be ISO string
    assert row_data["last_used_at"] == "2024-01-15T12:00:00"
    # float stays float
    assert abs(row_data["confidence"] - 3.14) < 1e-9
    # bool stays bool
    assert row_data["enabled"] is True
    # None stays None
    assert row_data["metadata"] is None


def test_serialize_metadata_column(auth_client, db_session):
    """_serialize must emit the dict under the DB column name 'metadata', not 'meta'.

    This is a regression guard for the bug where col.key == "metadata" caused
    getattr(row, "metadata") to resolve to SQLAlchemy's MetaData registry object,
    silently replacing the real dict with the string "MetaData()".
    """
    from app.domain.ai import ChatMessage
    from app.domain.ai_memory import AiMemory

    principal = _make_principal(auth_client)

    mem = AiMemory(
        workspace_id=principal.workspace_id,
        category="Profile",
        title="meta-test",
        content="checking metadata column",
        source="manual",
        sensitivity="LOW",
        meta={"k": "v", "num": 42},
    )
    db_session.add(mem)

    # Use a real session_id UUID for the ChatMessage
    import uuid as _uuid
    msg = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=_uuid.uuid4(),
        role="user",
        content="hello",
        meta={"msg_key": "msg_val"},
    )
    db_session.add(msg)
    db_session.commit()

    captured_bodies: dict[str, list] = {}

    def fake_urlopen(req, timeout=None):
        table = req.get_full_url().split("/rest/v1/")[1]
        captured_bodies[table] = json.loads(req.data.decode())
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        return fake_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        supabase_sync_service._do_sync(
            db_session,
            "https://abc.supabase.co",
            "key",
            str(principal.workspace_id),
        )

    # AiMemory.meta → column "metadata" must contain the real dict
    assert "ai_memories" in captured_bodies
    mem_row = captured_bodies["ai_memories"][0]
    assert "metadata" in mem_row, f"'metadata' key missing from ai_memories row: {list(mem_row)}"
    assert mem_row["metadata"] == {"k": "v", "num": 42}, (
        f"Expected dict but got: {mem_row['metadata']!r}"
    )

    # ChatMessage.meta → column "metadata" must contain the real dict
    assert "chat_messages" in captured_bodies
    msg_row = captured_bodies["chat_messages"][0]
    assert "metadata" in msg_row, f"'metadata' key missing from chat_messages row: {list(msg_row)}"
    assert msg_row["metadata"] == {"msg_key": "msg_val"}, (
        f"Expected dict but got: {msg_row['metadata']!r}"
    )


def test_serialize_datetime_and_uuid(auth_client, db_session):
    """_do_sync serializes datetime → isoformat string and UUID → str."""
    from app.domain.ai_memory import AiMemory

    principal = _make_principal(auth_client)
    mem = AiMemory(
        workspace_id=principal.workspace_id,
        category="Profile",
        title="Test",
        content="Content",
        source="manual",
        sensitivity="LOW",
    )
    db_session.add(mem)
    db_session.commit()
    db_session.refresh(mem)

    captured_bodies: dict[str, list] = {}

    def fake_urlopen(req, timeout=None):
        table = req.get_full_url().split("/rest/v1/")[1]
        body = json.loads(req.data.decode())
        captured_bodies[table] = body
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        return fake_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        supabase_sync_service._do_sync(
            db_session,
            "https://abc.supabase.co",
            "secret-key",
            str(principal.workspace_id),
        )

    assert "ai_memories" in captured_bodies
    row_data = captured_bodies["ai_memories"][0]
    # Both id and workspace_id must be strings (UUIDs serialised)
    assert isinstance(row_data["id"], str)
    assert isinstance(row_data["workspace_id"], str)
    # created_at must be an ISO-formatted string
    assert isinstance(row_data["created_at"], str)
    assert "T" in row_data["created_at"] or "-" in row_data["created_at"]


# ---------------------------------------------------------------------------
# _do_sync: URL, headers, body content, empty-table skip
# ---------------------------------------------------------------------------


def test_do_sync_posts_to_correct_tables(auth_client, db_session):
    """_do_sync POSTs to ai_memories and chat_sessions (at minimum) when rows exist."""
    from app.domain.ai import ChatSession
    from app.domain.ai_memory import AiMemory

    principal = _make_principal(auth_client)

    mem = AiMemory(
        workspace_id=principal.workspace_id,
        category="Goals",
        title="Sync target",
        content="Will be synced",
        source="manual",
        sensitivity="LOW",
    )
    db_session.add(mem)

    session = ChatSession(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        title="Test session",
    )
    db_session.add(session)
    db_session.commit()

    posted_tables: list[str] = []
    posted_headers: dict[str, dict] = {}
    posted_bodies: dict[str, list] = {}

    def fake_urlopen(req, timeout=None):
        table = req.get_full_url().split("/rest/v1/")[1]
        posted_tables.append(table)
        posted_headers[table] = dict(req.headers)
        posted_bodies[table] = json.loads(req.data.decode())
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        return fake_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        supabase_sync_service._do_sync(
            db_session,
            "https://abc.supabase.co",
            "my-secret-anon-key",
            str(principal.workspace_id),
        )

    assert "ai_memories" in posted_tables
    assert "chat_sessions" in posted_tables

    for table in ("ai_memories", "chat_sessions"):
        hdrs = posted_headers[table]
        # urllib may title-case header names; normalise to lowercase for comparison.
        normalised = {k.lower(): v for k, v in hdrs.items()}
        assert normalised.get("apikey") == "my-secret-anon-key", (
            f"apikey header missing or wrong in {table}: {normalised}"
        )
        assert "merge-duplicates" in normalised.get("prefer", ""), (
            f"Prefer header missing in {table}: {normalised}"
        )
        assert normalised.get("content-type", "").startswith("application/json"), (
            f"Content-Type wrong in {table}: {normalised}"
        )

    memory_ids = [r["id"] for r in posted_bodies["ai_memories"]]
    assert str(mem.id) in memory_ids

    session_ids = [r["id"] for r in posted_bodies["chat_sessions"]]
    assert str(session.id) in session_ids


def test_do_sync_skips_empty_tables(auth_client, db_session):
    """_do_sync must NOT send requests for empty product tables."""
    principal = _make_principal(auth_client)

    posted_tables: list[str] = []

    def fake_urlopen(req, timeout=None):
        posted_tables.append(req.get_full_url().split("/rest/v1/")[1])
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        return fake_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        supabase_sync_service._do_sync(
            db_session,
            "https://abc.supabase.co",
            "key",
            str(principal.workspace_id),
        )

    baseline_tables = {"workspaces", "workspace_members", "profiles", "audit_logs"}
    unexpected = set(posted_tables) - baseline_tables
    assert unexpected == set(), f"Expected only baseline workspace tables but got: {posted_tables}"


def test_do_sync_body_is_valid_json_list(auth_client, db_session):
    """The request body sent to Supabase must be a JSON-encoded list of objects."""
    from app.domain.ai_memory import AiMemory

    principal = _make_principal(auth_client)
    mem = AiMemory(
        workspace_id=principal.workspace_id,
        category="Technical",
        title="JSON test",
        content="Checking JSON body",
        source="manual",
        sensitivity="LOW",
    )
    db_session.add(mem)
    db_session.commit()

    captured_data: dict[str, bytes] = {}

    def fake_urlopen(req, timeout=None):
        table = req.get_full_url().split("/rest/v1/")[1]
        captured_data[table] = req.data
        fake_resp = MagicMock()
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        return fake_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        supabase_sync_service._do_sync(
            db_session,
            "https://abc.supabase.co",
            "key",
            str(principal.workspace_id),
        )

    assert "ai_memories" in captured_data
    body = json.loads(captured_data["ai_memories"].decode())
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["title"] == "JSON test"


# ---------------------------------------------------------------------------
# Endpoint: POST /ai/memory/sync/supabase → not_configured (module present)
# ---------------------------------------------------------------------------


def test_endpoint_sync_supabase_not_configured(auth_client):
    """With the module present and no creds, the endpoint must return 'not_configured'."""
    resp = auth_client.post(f"{API}/ai/memory/sync/supabase")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "not_configured", (
        f"Expected 'not_configured' but got {data['status']!r}"
    )


# ---------------------------------------------------------------------------
# URL scheme validation: non-http(s) URLs must be treated as not_configured
# ---------------------------------------------------------------------------


def test_sync_all_rejects_non_http_url(auth_client, db_session):
    """sync_all must return 'not_configured' for URLs that are not http:// or https://.

    urllib also accepts file:// and ftp://, which could be exploited; we reject them.
    """
    from sqlalchemy import delete

    from app.domain.integrations import IntegrationConfig

    principal = _make_principal(auth_client)

    for bad_url in ("file:///etc/passwd", "ftp://example.com/db", "javascript:alert(1)"):
        _insert_integration_row(
            db_session,
            principal,
            url=bad_url,
            anon_key="some-key",
            enabled=True,
        )
        with patch.object(threading.Thread, "start") as mock_start:
            result = supabase_sync_service.sync_all(db_session, principal)

        assert result["status"] == "not_configured", (
            f"Expected 'not_configured' for URL {bad_url!r} but got {result['status']!r}"
        )
        mock_start.assert_not_called()

        # Remove the integration row before the next iteration
        db_session.execute(
            delete(IntegrationConfig).where(
                IntegrationConfig.workspace_id == principal.workspace_id,
                IntegrationConfig.provider_id == "supabase",
            )
        )
        db_session.commit()
