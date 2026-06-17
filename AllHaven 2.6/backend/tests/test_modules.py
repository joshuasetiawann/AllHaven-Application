"""Tests for the unlocked MVP modules: calendar, drive, weather, automations."""

import io

from tests.conftest import API


# --- Calendar -------------------------------------------------------------

def test_calendar_event_crud_persists(auth_client):
    created = auth_client.post(
        f"{API}/calendar/events",
        json={"title": "Standup", "start_at": "2026-06-10T09:00:00Z"},
    )
    assert created.status_code == 200, created.text
    event_id = created.json()["data"]["id"]

    listed = auth_client.get(f"{API}/calendar/events").json()["data"]
    assert any(e["id"] == event_id for e in listed)

    updated = auth_client.put(
        f"{API}/calendar/events/{event_id}", json={"title": "Daily Standup"}
    )
    assert updated.json()["data"]["title"] == "Daily Standup"

    auth_client.delete(f"{API}/calendar/events/{event_id}")
    listed = auth_client.get(f"{API}/calendar/events").json()["data"]
    assert not any(e["id"] == event_id for e in listed)


# --- Drive ----------------------------------------------------------------

def test_drive_upload_list_download_delete(auth_client):
    files = {"file": ("hello.txt", io.BytesIO(b"hello world"), "text/plain")}
    up = auth_client.post(f"{API}/drive/files", files=files)
    assert up.status_code == 200, up.text
    file_id = up.json()["data"]["id"]
    assert up.json()["data"]["size_bytes"] == 11

    listed = auth_client.get(f"{API}/drive/files").json()["data"]
    assert any(f["id"] == file_id for f in listed)

    dl = auth_client.get(f"{API}/drive/files/{file_id}/download")
    assert dl.status_code == 200
    assert dl.content == b"hello world"

    auth_client.delete(f"{API}/drive/files/{file_id}")
    listed = auth_client.get(f"{API}/drive/files").json()["data"]
    assert not any(f["id"] == file_id for f in listed)


def test_drive_path_traversal_blocked(auth_client):
    # A malicious filename must not escape the storage root; it is reduced to a
    # safe basename and the stored metadata reflects that.
    files = {"file": ("../../../../etc/passwd", io.BytesIO(b"x"), "text/plain")}
    up = auth_client.post(f"{API}/drive/files", files=files)
    assert up.status_code == 200, up.text
    assert "/" not in up.json()["data"]["filename"]
    assert ".." not in up.json()["data"]["filename"]


# --- Weather --------------------------------------------------------------

def test_weather_setup_required_when_unconfigured(auth_client):
    resp = auth_client.get(f"{API}/weather/current?location=Jakarta")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "setup_required"


def test_weather_location_persists(auth_client):
    auth_client.post(f"{API}/weather/locations", json={"name": "Jakarta", "is_default": True})
    rows = auth_client.get(f"{API}/weather/locations").json()["data"]
    assert any(r["name"] == "Jakarta" and r["is_default"] for r in rows)


# --- Automations ----------------------------------------------------------

def test_automation_crud_persists_disabled_safe(auth_client):
    created = auth_client.post(
        f"{API}/automations",
        json={"name": "Nightly backup", "trigger_type": "schedule", "action_type": "noop"},
    )
    assert created.status_code == 200, created.text
    # Created disabled-safe; AllHaven never auto-runs it.
    assert created.json()["data"]["enabled"] is False
    automation_id = created.json()["data"]["id"]

    listed = auth_client.get(f"{API}/automations").json()["data"]
    assert any(a["id"] == automation_id for a in listed)

    auth_client.delete(f"{API}/automations/{automation_id}")
    listed = auth_client.get(f"{API}/automations").json()["data"]
    assert not any(a["id"] == automation_id for a in listed)
