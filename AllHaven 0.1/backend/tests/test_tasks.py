"""Tasks CRUD tests."""

from tests.conftest import API


def test_tasks_require_auth(client):
    assert client.get(f"{API}/tasks").status_code == 401


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
