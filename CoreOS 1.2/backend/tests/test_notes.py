"""Notes CRUD tests."""

from tests.conftest import API


def test_note_crud_and_tags(auth_client):
    created = auth_client.post(
        f"{API}/notes",
        json={
            "title": "Roadmap",
            "content": "Q3 plan",
            "tags": ["planning", "planning", " strategy "],
            "is_pinned": True,
        },
    )
    assert created.status_code == 200, created.text
    note = created.json()["data"]
    # Tags are de-duplicated and trimmed.
    assert note["tags"] == ["planning", "strategy"]
    assert note["is_pinned"] is True
    note_id = note["id"]

    # Update
    updated = auth_client.patch(f"{API}/notes/{note_id}", json={"title": "Roadmap v2"})
    assert updated.json()["data"]["title"] == "Roadmap v2"

    # Tag filter
    filtered = auth_client.get(f"{API}/notes", params={"tag": "strategy"})
    assert len(filtered.json()["data"]) == 1
    assert auth_client.get(f"{API}/notes", params={"tag": "missing"}).json()["data"] == []

    # Soft delete
    assert auth_client.delete(f"{API}/notes/{note_id}").status_code == 200
    assert auth_client.get(f"{API}/notes/{note_id}").status_code == 404
