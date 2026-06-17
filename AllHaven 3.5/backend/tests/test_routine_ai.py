"""Tests for AI routine generation, atomic batch create, and sync status."""

import app.services.ai_provider_router as _router
from tests.conftest import API


def _count_routines(auth_client) -> int:
    return len(auth_client.get(f"{API}/routines/events").json()["data"])


def _fake_run_chat(content: str):
    def _run(db, principal, *, messages, provider_id=None):
        return {"ok": True, "content": content, "error": ""}

    return _run


def _fake_run_chat_error(error: str, content: str):
    def _run(db, principal, *, messages, provider_id=None):
        return {"ok": False, "content": content, "error": error}

    return _run


# --- Generate -------------------------------------------------------------

def test_generate_without_provider_returns_clear_state(auth_client):
    """No AI provider configured (default test env) → honest, not-saved state."""
    resp = auth_client.post(
        f"{API}/routines/generate",
        json={"prompt": "deep work morning", "date": "2026-06-13", "period": "morning"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "not_configured"
    assert data["message"] == "Configure AI provider first."
    assert data["drafts"] == []


def test_generate_disabled_provider_keeps_specific_message(auth_client, monkeypatch):
    """A configured-but-disabled provider must not be reported as 'not_configured'.

    run_chat returns error='disabled' with a specific, actionable message; the
    service must surface it (status='blocked') instead of the misleading
    'Configure AI provider first.' — the user already configured it.
    """
    specific = "The 'Anthropic' provider is configured but disabled. Enable it in Settings to use it."
    monkeypatch.setattr(_router, "run_chat", _fake_run_chat_error("disabled", specific))

    resp = auth_client.post(
        f"{API}/routines/generate",
        json={"prompt": "morning", "date": "2026-06-13", "period": "morning"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "blocked"
    assert data["message"] == specific
    assert data["drafts"] == []


def test_generate_returns_validated_drafts_without_saving(auth_client, monkeypatch):
    before = _count_routines(auth_client)
    content = (
        '[{"title": "Deep work", "time": "08:00", "duration_minutes": 90, '
        '"repeat_rule": "daily", "repeat_days": ["mon", "tue"]}, '
        '{"title": "Out of slot", "time": "21:00"}]'
    )
    monkeypatch.setattr(_router, "run_chat", _fake_run_chat(content))

    resp = auth_client.post(
        f"{API}/routines/generate",
        json={"prompt": "plan my morning", "date": "2026-06-13", "period": "morning"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "ok"
    assert len(data["drafts"]) == 2

    first = data["drafts"][0]
    assert first["title"] == "Deep work"
    assert first["start_at"].endswith("08:00:00")
    assert first["end_at"].endswith("09:30:00")
    assert first["time_period"] == "morning"
    assert first["repeat_rule"] == "daily"
    assert first["repeat_days"] == ["mon", "tue"]

    # 21:00 is outside the morning window → snapped to the morning default (07:00).
    assert data["drafts"][1]["start_at"].endswith("07:00:00")

    # Generation must NEVER write to the database.
    assert _count_routines(auth_client) == before


def test_generate_caps_drafts_at_eight(auth_client, monkeypatch):
    items = ", ".join(
        f'{{"title": "Item {i}", "time": "0{(i % 6) + 5}:00"}}' for i in range(15)
    )
    monkeypatch.setattr(_router, "run_chat", _fake_run_chat(f"[{items}]"))

    resp = auth_client.post(
        f"{API}/routines/generate",
        json={"prompt": "many things", "date": "2026-06-13", "period": "morning"},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]["drafts"]) == 8


def test_generate_unparseable_output_is_clear_error(auth_client, monkeypatch):
    monkeypatch.setattr(_router, "run_chat", _fake_run_chat("sorry, I can't help with that"))
    resp = auth_client.post(
        f"{API}/routines/generate",
        json={"prompt": "x", "date": "2026-06-13", "period": "morning"},
    )
    data = resp.json()["data"]
    assert data["status"] == "error"
    assert data["drafts"] == []
    assert data["message"]


def test_generate_rejects_bad_date(auth_client):
    resp = auth_client.post(
        f"{API}/routines/generate",
        json={"prompt": "x", "date": "13-06-2026", "period": "morning"},
    )
    assert resp.status_code == 422, resp.text


# --- Atomic batch create --------------------------------------------------

def test_batch_create_saves_all_valid_items(auth_client):
    before = _count_routines(auth_client)
    resp = auth_client.post(
        f"{API}/routines/events/batch",
        json={
            "items": [
                {"title": "Batch A", "start_at": "2026-06-13T07:00:00Z", "time_period": "morning"},
                {"title": "Batch B", "start_at": "2026-06-13T13:00:00Z", "time_period": "afternoon"},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == 2
    assert _count_routines(auth_client) == before + 2


def test_batch_create_is_atomic_when_one_item_invalid(auth_client):
    """An item that passes schema but fails domain validation rolls back the whole batch."""
    before = _count_routines(auth_client)
    resp = auth_client.post(
        f"{API}/routines/events/batch",
        json={
            "items": [
                {"title": "Valid first", "start_at": "2026-06-13T07:00:00Z"},
                # 'funday' is a str (passes pydantic) but not a real weekday → domain error.
                {"title": "Invalid days", "start_at": "2026-06-13T08:00:00Z", "repeat_days": ["funday"]},
            ]
        },
    )
    assert resp.status_code in (400, 422), resp.text
    # Nothing was persisted — not even the valid first item.
    assert _count_routines(auth_client) == before


def test_batch_create_rejects_empty(auth_client):
    resp = auth_client.post(f"{API}/routines/events/batch", json={"items": []})
    assert resp.status_code == 422, resp.text


# --- Sync status ----------------------------------------------------------

def test_sync_status_defaults_to_local_first(auth_client):
    resp = auth_client.get(f"{API}/routines/sync-status")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "local_first"
    assert data["configured"] is False
