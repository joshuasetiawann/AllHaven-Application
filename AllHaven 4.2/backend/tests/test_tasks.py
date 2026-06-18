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


# ---------------------------------------------------------------------------
# Soft-delete sync-correctness tests (fix: resurrection / cap-skew blockers)
# ---------------------------------------------------------------------------


def test_delete_checklist_item_is_soft_delete(auth_client, db_session):
    """DELETE /checklist/:id must mark is_deleted=True, not physically remove the row."""
    from app.domain.tasks import TaskChecklistItem
    from sqlalchemy import select

    created = auth_client.post(f"{API}/tasks", json={"title": "S", "checklist": ["X"]})
    item_id = created.json()["data"]["checklist_items"][0]["id"]
    task_id = created.json()["data"]["id"]

    auth_client.delete(f"{API}/tasks/{task_id}/checklist/{item_id}")

    # The row must still exist in the DB.
    import uuid
    row = db_session.scalar(
        select(TaskChecklistItem).where(TaskChecklistItem.id == uuid.UUID(item_id))
    )
    assert row is not None, "Row was physically deleted — must be soft-deleted instead."
    assert row.is_deleted is True
    assert row.deleted_at is not None


def test_deleted_checklist_item_excluded_from_response(auth_client):
    """After deleting an item, the API response checklist_items must exclude the tombstone."""
    created = auth_client.post(f"{API}/tasks", json={"title": "T", "checklist": ["keep", "drop"]})
    task_id = created.json()["data"]["id"]
    items = created.json()["data"]["checklist_items"]
    drop_id = items[1]["id"]
    keep_id = items[0]["id"]

    result = auth_client.delete(f"{API}/tasks/{task_id}/checklist/{drop_id}")
    returned_ids = [i["id"] for i in result.json()["data"]["checklist_items"]]
    assert keep_id in returned_ids
    assert drop_id not in returned_ids

    # GET the task fresh — tombstone must still be hidden.
    fetched = auth_client.get(f"{API}/tasks/{task_id}")
    fetched_ids = [i["id"] for i in fetched.json()["data"]["checklist_items"]]
    assert drop_id not in fetched_ids


def test_mutating_deleted_item_raises_not_found(auth_client):
    """Update and delete on an already-deleted item must return 404 (no tombstone mutation)."""
    created = auth_client.post(f"{API}/tasks", json={"title": "T", "checklist": ["item"]})
    task_id = created.json()["data"]["id"]
    item_id = created.json()["data"]["checklist_items"][0]["id"]

    # First delete succeeds.
    first = auth_client.delete(f"{API}/tasks/{task_id}/checklist/{item_id}")
    assert first.status_code == 200

    # Second delete on the tombstone must be 404.
    second_delete = auth_client.delete(f"{API}/tasks/{task_id}/checklist/{item_id}")
    assert second_delete.status_code == 404

    # Update on the tombstone must also be 404.
    update_resp = auth_client.patch(
        f"{API}/tasks/{task_id}/checklist/{item_id}", json={"is_done": True}
    )
    assert update_resp.status_code == 404


def test_soft_deleted_items_do_not_count_toward_cap_or_skew_position(auth_client):
    """Tombstones must not count toward the MAX_CHECKLIST_ITEMS=5 cap or inflate positions."""
    # Create a task with 5 items (at the cap).
    items_titles = ["a", "b", "c", "d", "e"]
    created = auth_client.post(
        f"{API}/tasks", json={"title": "Cap test", "checklist": items_titles}
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["id"]
    items = created.json()["data"]["checklist_items"]
    assert len(items) == 5

    # Delete one item — now only 4 active items, 1 tombstone.
    delete_id = items[2]["id"]  # position 2, "c"
    auth_client.delete(f"{API}/tasks/{task_id}/checklist/{delete_id}")

    # Should now be possible to add a 5th active item (tombstone doesn't count).
    added = auth_client.post(f"{API}/tasks/{task_id}/checklist", json={"title": "f"})
    assert added.status_code == 200, added.text
    active_items = added.json()["data"]["checklist_items"]
    assert len(active_items) == 5  # 4 survivors + 1 new = 5

    # Position of the new item must be max(active positions) + 1 (not inflated by tombstone).
    # The 5 active items had positions 0,1,3,4; next should be 5.
    new_item = next(i for i in active_items if i["title"] == "f")
    active_positions = sorted(i["position"] for i in active_items)
    assert new_item["position"] == max(active_positions)  # highest position == the new item's

    # Now at cap again — adding a 6th active item must be rejected.
    over_cap = auth_client.post(f"{API}/tasks/{task_id}/checklist", json={"title": "g"})
    assert over_cap.status_code == 400
    assert over_cap.json()["error_code"] == "CHECKLIST_LIMIT"
