"""Tasks CRUD tests."""

from tests.conftest import API


def test_tasks_require_auth(client):
    assert client.get(f"{API}/tasks").status_code == 401


def test_create_task_with_checklist_and_complete_reopen(auth_client):
    created = auth_client.post(
        f"{API}/tasks",
        json={"title": "Launch checklist", "checklist": ["Plan", "Build", "Ship"]},
    )
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    assert len(task["checklist_items"]) == 3
    task_id = task["id"]

    # Complete sets DONE + completed_at.
    done = auth_client.post(f"{API}/tasks/{task_id}/complete")
    assert done.status_code == 200
    assert done.json()["data"]["status"] == "DONE"
    assert done.json()["data"]["completed_at"] is not None

    # Reopen clears completed_at.
    reopened = auth_client.post(f"{API}/tasks/{task_id}/reopen")
    assert reopened.json()["data"]["status"] == "TODO"
    assert reopened.json()["data"]["completed_at"] is None


def test_checklist_max_five_enforced(auth_client):
    # Five via create.
    created = auth_client.post(
        f"{API}/tasks",
        json={"title": "Five", "checklist": ["a", "b", "c", "d", "e"]},
    )
    task_id = created.json()["data"]["id"]
    assert len(created.json()["data"]["checklist_items"]) == 5

    # Sixth via endpoint is rejected.
    sixth = auth_client.post(f"{API}/tasks/{task_id}/checklist", json={"title": "f"})
    assert sixth.status_code == 400
    assert sixth.json()["error_code"] == "CHECKLIST_LIMIT"


def test_create_task_rejects_more_than_five_checklist(auth_client):
    resp = auth_client.post(
        f"{API}/tasks",
        json={"title": "Too many", "checklist": ["1", "2", "3", "4", "5", "6"]},
    )
    assert resp.status_code == 422


def test_checklist_item_toggle_and_delete(auth_client):
    created = auth_client.post(f"{API}/tasks", json={"title": "T", "checklist": ["one"]})
    task_id = created.json()["data"]["id"]
    item_id = created.json()["data"]["checklist_items"][0]["id"]

    toggled = auth_client.patch(
        f"{API}/tasks/{task_id}/checklist/{item_id}", json={"is_done": True}
    )
    assert toggled.json()["data"]["checklist_items"][0]["is_done"] is True

    deleted = auth_client.delete(f"{API}/tasks/{task_id}/checklist/{item_id}")
    assert deleted.json()["data"]["checklist_items"] == []


def test_task_crud_lifecycle(auth_client):
    # Create
    created = auth_client.post(
        f"{API}/tasks",
        json={"title": "Write report", "priority": "high"},
    )
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    assert task["title"] == "Write report"
    assert task["priority"] == "HIGH"
    assert task["status"] == "TODO"
    task_id = task["id"]

    # List
    listing = auth_client.get(f"{API}/tasks")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1

    # Get
    fetched = auth_client.get(f"{API}/tasks/{task_id}")
    assert fetched.status_code == 200

    # Update -> DONE sets completed_at
    updated = auth_client.patch(f"{API}/tasks/{task_id}", json={"status": "done"})
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "DONE"
    assert updated.json()["data"]["completed_at"] is not None

    # Soft delete
    deleted = auth_client.delete(f"{API}/tasks/{task_id}")
    assert deleted.status_code == 200
    assert auth_client.get(f"{API}/tasks/{task_id}").status_code == 404
    assert auth_client.get(f"{API}/tasks").json()["data"] == []


def test_task_invalid_status_rejected(auth_client):
    resp = auth_client.post(f"{API}/tasks", json={"title": "x", "status": "NONSENSE"})
    assert resp.status_code == 422
