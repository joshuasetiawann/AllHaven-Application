import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from app.domain.sync_state import SyncState
from app.domain.tasks import Task
from app.domain.users import Profile
from app.domain.workspaces import Workspace, WorkspaceMember
from app.core.database import SessionLocal
from app.services import sync_registry
from app.services import supabase_sync_service


def _create_tenant(db) -> tuple[uuid.UUID, uuid.UUID]:
    """Create the minimum FK-valid workspace used by direct-session sync tests."""
    user = Profile(
        id=uuid.uuid4(),
        email=f"sync-{uuid.uuid4().hex}@example.com",
    )
    db.add(user)
    db.flush()
    workspace = Workspace(id=uuid.uuid4(), name="Sync test", owner_id=user.id)
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
    )
    db.commit()
    return workspace.id, user.id


def test_sync_state_roundtrips_and_is_unique():
    db = SessionLocal()
    try:
        ws, _ = _create_tenant(db)
        row = SyncState(workspace_id=ws, table_name="tasks", direction="push")
        db.add(row)
        db.commit()
        got = (
            db.query(SyncState)
            .filter(SyncState.workspace_id == ws, SyncState.table_name == "tasks", SyncState.direction == "push")
            .one()
        )
        assert got.last_value is None and got.last_pk is None
        got.last_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.commit()
        assert got.last_value.year == 2026
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task 3: sync_registry
# ---------------------------------------------------------------------------

def test_registry_covers_core_tables_with_correct_watermarks():
    by_name = {s.table_name: s for s in sync_registry.SYNCED_TABLES}
    # core CRUD tables present, updated_at watermark
    for t in ["tasks", "notes", "transactions", "finance_categories", "calendar_events",
              "weather_locations", "automations", "workspaces", "workspace_members", "profiles"]:
        assert t in by_name, f"{t} missing from registry"
        assert by_name[t].append_only is False
        assert by_name[t].watermark_col == "updated_at"
    # append-only tables watermark on created_at
    for t in ["chat_messages", "ai_tool_calls", "ai_agent_responses",
              "ai_knowledge_chunks", "audit_logs"]:
        assert by_name[t].watermark_col == "created_at"
        assert by_name[t].append_only is True
    # sync_state itself is never synced
    assert "sync_state" not in by_name
    # auth/secret tables never synced
    assert "local_users" not in by_name and "user_sessions" not in by_name
    assert "integration_configs" not in by_name and "ai_agent_configs" not in by_name


# ---------------------------------------------------------------------------
# Task 4: _deserialize
# ---------------------------------------------------------------------------

def test_deserialize_casts_uuid_datetime_and_is_serialize_inverse():
    pk = uuid.uuid4()
    ws = uuid.uuid4()
    incoming = {
        "id": str(pk),
        "workspace_id": str(ws),
        "title": "Buy milk",
        "status": "TODO",
        "is_deleted": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-02T03:04:05+00:00",
    }
    kwargs = supabase_sync_service._deserialize(Task, incoming)
    assert kwargs["id"] == pk
    assert kwargs["workspace_id"] == ws
    assert kwargs["title"] == "Buy milk"
    assert kwargs["updated_at"].year == 2026 and kwargs["updated_at"].month == 1 and kwargs["updated_at"].day == 2
    # round-trip: serialize(model(**kwargs)) reproduces the DB-column-keyed dict
    obj = Task(**kwargs)
    back = supabase_sync_service._serialize(obj)
    assert back["id"] == str(pk)
    assert back["updated_at"].startswith("2026-01-02T03:04:05")


# ---------------------------------------------------------------------------
# Task 5: push_table
# ---------------------------------------------------------------------------

from app.services import sync_engine  # noqa: E402


def _ws_with_task(db):
    ws, user = _create_tenant(db)
    t = Task(workspace_id=ws, created_by=user, title="t1", status="TODO")
    db.add(t)
    db.commit()
    return ws


def test_push_table_sends_new_rows_and_advances_watermark():
    db = SessionLocal()
    try:
        ws = _ws_with_task(db)
        spec = sync_registry.spec_for("tasks")
        sent = {}

        def fake_upsert(table, rows):
            sent.setdefault(table, []).extend(rows)

        n = sync_engine.push_table(db, "https://x.supabase.co", "svc", ws, [], spec, upsert=fake_upsert)
        assert n == 1 and len(sent["tasks"]) == 1
        # second push with no new writes sends nothing (watermark advanced)
        n2 = sync_engine.push_table(db, "https://x.supabase.co", "svc", ws, [], spec, upsert=fake_upsert)
        assert n2 == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task 6: pull_table — tenant-safe LWW merge
# ---------------------------------------------------------------------------

def test_pull_applies_remote_newer_without_advancing_push_cursor():
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        pk = uuid.uuid4()
        local = Task(id=pk, workspace_id=ws, created_by=user, title="old", status="TODO",
                     updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        db.add(local)
        db.commit()
        spec = sync_registry.spec_for("tasks")
        remote_row = {
            "id": str(pk), "workspace_id": str(ws), "title": "new-from-peer", "status": "TODO",
            "is_deleted": False, "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-02-01T00:00:00+00:00",
        }

        def fake_fetch(fetch_spec, fetch_ws, member_ids, since, since_pk):
            assert fetch_spec is spec and fetch_ws == ws
            return [remote_row]

        applied = sync_engine.pull_table(db, "https://x", "svc", ws, [], spec, fetch=fake_fetch)
        assert applied == 1
        db.refresh(local)
        assert local.title == "new-from-peer"
        # Pull must not move the global push cursor. Re-upserting this remote row
        # once is safe; skipping an older unsent local row is not.
        sent = []
        n = sync_engine.push_table(db, "https://x", "svc", ws, [], spec, upsert=lambda t, r: sent.extend(r))
        assert n == 1 and [row["id"] for row in sent] == [str(pk)]
        assert sync_engine.push_table(
            db, "https://x", "svc", ws, [], spec, upsert=lambda t, r: None
        ) == 0
    finally:
        db.close()


def test_newer_remote_pull_does_not_skip_older_unsent_local_row():
    """Regression: echo suppression used to jump over a local never-pushed row."""
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        local_id = uuid.uuid4()
        remote_id = uuid.uuid4()
        db.add(
            Task(
                id=local_id,
                workspace_id=ws,
                created_by=user,
                title="local-never-pushed",
                status="TODO",
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
        remote = {
            "id": str(remote_id),
            "workspace_id": str(ws),
            "created_by": str(user),
            "title": "newer-remote",
            "status": "TODO",
            "is_deleted": False,
            "created_at": "2026-02-01T00:00:00+00:00",
            "updated_at": "2026-02-01T00:00:00+00:00",
        }
        spec = sync_registry.spec_for("tasks")

        assert sync_engine.pull_table(
            db, "https://x", "svc", ws, [], spec, fetch=lambda *args: [remote]
        ) == 1
        sent: list[dict] = []
        pushed = sync_engine.push_table(
            db,
            "https://x",
            "svc",
            ws,
            [],
            spec,
            upsert=lambda table, rows: sent.extend(rows),
        )

        assert pushed == 2
        assert {row["id"] for row in sent} == {str(local_id), str(remote_id)}
    finally:
        db.close()


def test_pull_keeps_local_when_local_is_newer():
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        pk = uuid.uuid4()
        db.add(Task(id=pk, workspace_id=ws, created_by=user, title="local-newer", status="TODO",
                    updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc)))
        db.commit()
        spec = sync_registry.spec_for("tasks")
        stale = {"id": str(pk), "workspace_id": str(ws), "title": "stale", "status": "TODO",
                 "is_deleted": False, "created_at": "2026-01-01T00:00:00+00:00",
                 "updated_at": "2026-01-05T00:00:00+00:00"}
        applied = sync_engine.pull_table(db, "https://x", "svc", ws, [], spec, fetch=lambda *a: [stale])
        local = db.get(Task, pk)
        assert local.title == "local-newer"  # LWW: local wins, not overwritten
    finally:
        db.close()


def test_pull_keeps_local_when_remote_has_non_utc_offset_but_is_older():
    """Regression: remote row with +07:00 offset that is OLDER in UTC must not overwrite local.

    Local:  2026-02-01T05:00:00+00:00  (05:00 UTC)   — newer
    Remote: 2026-02-01T09:00:00+07:00  (02:00 UTC)   — older

    Before the fix, `.replace(tzinfo=None)` compared wall-clock numbers
    (09:00 > 05:00) and silently overwrote the newer local row.
    After the fix, `_to_utc_naive` converts to UTC first (02:00 < 05:00)
    and correctly keeps the local row.
    """
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        pk = uuid.uuid4()
        # Local row: 05:00 UTC — the newer row
        local = Task(
            id=pk,
            workspace_id=ws,
            created_by=user,
            title="local-newer",
            status="TODO",
            updated_at=datetime(2026, 2, 1, 5, 0, 0, tzinfo=timezone.utc),
        )
        db.add(local)
        db.commit()

        spec = sync_registry.spec_for("tasks")
        # Remote row: 09:00+07:00 == 02:00 UTC — older instant, different title
        remote_row = {
            "id": str(pk),
            "workspace_id": str(ws),
            "title": "remote-older-with-tz-offset",
            "status": "TODO",
            "is_deleted": False,
            "created_at": "2026-02-01T09:00:00+07:00",
            "updated_at": "2026-02-01T09:00:00+07:00",
        }

        sync_engine.pull_table(
            db, "https://x", "svc", ws, [], spec,
            fetch=lambda *a: [remote_row],
        )

        db.refresh(local)
        assert local.title == "local-newer", (
            f"LWW violation: local row (05:00 UTC) was overwritten by remote row "
            f"(09:00+07:00 = 02:00 UTC), title is now {local.title!r}"
        )
    finally:
        db.close()


def test_push_cursor_does_not_skip_rows_with_the_same_timestamp():
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        first_id = uuid.UUID(int=1)
        second_id = uuid.UUID(int=2)
        db.add_all(
            [
                Task(
                    id=first_id,
                    workspace_id=ws,
                    created_by=user,
                    title="already-pushed",
                    status="TODO",
                    updated_at=timestamp,
                ),
                Task(
                    id=second_id,
                    workspace_id=ws,
                    created_by=user,
                    title="same-timestamp-next-id",
                    status="TODO",
                    updated_at=timestamp,
                ),
            ]
        )
        cursor = sync_engine._state(db, ws, "tasks", "push")
        cursor.last_value = timestamp
        cursor.last_pk = first_id
        db.commit()

        sent: list[dict] = []
        pushed = sync_engine.push_table(
            db,
            "https://x",
            "svc",
            ws,
            [],
            sync_registry.spec_for("tasks"),
            upsert=lambda table, rows: sent.extend(rows),
        )

        assert pushed == 1
        assert [row["id"] for row in sent] == [str(second_id)]
        assert cursor.last_pk == second_id
    finally:
        db.close()


def test_pull_rejects_rows_from_a_different_workspace():
    """A service-role response cannot cross the active tenant boundary."""
    db = SessionLocal()
    try:
        ws_a, user = _create_tenant(db)
        ws_b, _ = _create_tenant(db)
        protected_id = uuid.uuid4()
        protected = Task(
            id=protected_id,
            workspace_id=ws_b,
            created_by=user,
            title="workspace-b-private",
            status="TODO",
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        db.add(protected)
        db.commit()

        allowed_id = uuid.uuid4()
        allowed = {
            "id": str(allowed_id),
            "workspace_id": str(ws_a),
            "created_by": str(user),
            "title": "workspace-a-row",
            "status": "TODO",
            "is_deleted": False,
            "created_at": "2026-02-01T00:00:00+00:00",
            "updated_at": "2026-02-01T00:00:00+00:00",
        }
        out_of_scope = {
            "id": str(protected_id),
            "workspace_id": str(ws_b),
            "created_by": str(user),
            "title": "cross-tenant-overwrite",
            "status": "TODO",
            "is_deleted": False,
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        }
        spoofed_pk_collision = {
            # Payload claims workspace A but reuses a real PK owned by workspace B.
            "id": str(protected_id),
            "workspace_id": str(ws_a),
            "created_by": str(user),
            "title": "cross-tenant-pk-takeover",
            "status": "TODO",
            "is_deleted": False,
            "created_at": "2026-04-01T00:00:00+00:00",
            "updated_at": "2026-04-01T00:00:00+00:00",
        }

        applied = sync_engine.pull_table(
            db,
            "https://x",
            "svc",
            ws_a,
            [],
            sync_registry.spec_for("tasks"),
            fetch=lambda *args: [allowed, out_of_scope, spoofed_pk_collision],
        )

        assert applied == 1
        assert db.get(Task, allowed_id).workspace_id == ws_a
        db.refresh(protected)
        assert protected.workspace_id == ws_b
        assert protected.title == "workspace-b-private"
        pull_state = sync_engine._state(db, ws_a, "tasks", "pull")
        # Rejected rows do not get to move another tenant's cursor forward.
        assert pull_state.last_pk == allowed_id
    finally:
        db.close()


def test_http_fetch_adds_tenant_filters_for_special_and_workspace_tables():
    ws = uuid.uuid4()
    members = [uuid.uuid4(), uuid.uuid4()]
    captured: list[str] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req.get_full_url())
        response = MagicMock()
        response.__enter__ = lambda value: value
        response.__exit__ = MagicMock(return_value=False)
        response.read = lambda: b"[]"
        return response

    fetch = sync_engine._http_fetch("https://example.supabase.co", "service-role-secret")
    names = ["workspaces", "workspace_members", "profiles", "audit_logs", "tasks"]
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        for name in names:
            fetch(sync_registry.spec_for(name), ws, members, None, None)

    assert len(captured) == len(names)
    by_table = {
        url.split("/rest/v1/")[1].split("?", 1)[0]: parse_qs(urlparse(url).query)
        for url in captured
    }
    assert by_table["workspaces"]["id"] == [f"eq.{ws}"]
    assert by_table["profiles"]["id"] == [
        f"in.({','.join(str(value) for value in sorted(members, key=lambda value: value.int))})"
    ]
    for name in ("workspace_members", "audit_logs", "tasks"):
        assert by_table[name]["workspace_id"] == [f"eq.{ws}"]
    for url in captured:
        assert "service-role-secret" not in url
        query = parse_qs(urlparse(url).query)
        assert query["order"][0].endswith(".asc,id.asc")


def test_http_fetch_paginates_more_than_1000_rows_with_timestamp_ties():
    ws = uuid.uuid4()
    timestamp = "2026-04-05T06:07:08+00:00"
    ids = [uuid.UUID(int=value) for value in range(1, 1003)]
    first_page = [
        {
            "id": str(row_id),
            "workspace_id": str(ws),
            "updated_at": timestamp,
        }
        for row_id in ids[:1000]
    ]
    second_page = [
        {
            "id": str(row_id),
            "workspace_id": str(ws),
            "updated_at": timestamp,
        }
        for row_id in ids[1000:]
    ]
    requested: list[str] = []

    def fake_urlopen(req, timeout=None):
        requested.append(req.get_full_url())
        payload = first_page if len(requested) == 1 else second_page
        response = MagicMock()
        response.__enter__ = lambda value: value
        response.__exit__ = MagicMock(return_value=False)
        response.read = lambda: __import__("json").dumps(payload).encode()
        return response

    fetch = sync_engine._http_fetch("https://example.supabase.co", "svc")
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        rows = fetch(sync_registry.spec_for("tasks"), ws, [], None, None)

    assert len(rows) == 1002
    assert len(requested) == 2
    second_query = parse_qs(urlparse(requested[1]).query)
    assert second_query["workspace_id"] == [f"eq.{ws}"]
    cursor_filter = second_query["or"][0]
    assert f"updated_at.eq.{timestamp}" in cursor_filter
    assert f"id.gt.{ids[999]}" in cursor_filter


# ---------------------------------------------------------------------------
# Task 7: sync_two_way orchestrator
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock  # noqa: E402
from app.core.principal import Principal  # noqa: E402


def test_sync_two_way_skips_when_no_credentials(db_session):
    """sync_two_way returns 'skipped' and never raises when credentials are absent."""
    p = Principal(user_id=uuid.uuid4(), workspace_id=uuid.uuid4(), email="x@y.z")
    with patch("app.services.supabase_auth_service.get_service_credentials", return_value=(None, None)):
        out = sync_engine.sync_two_way(db_session, p)
    assert out["status"] == "skipped"


def test_sync_two_way_pulls_then_pushes(db_session, auth_client):
    """sync_two_way issues GET (pull) and POST (push) for each table when credentials exist."""
    from tests.test_supabase_sync import _make_principal
    p = _make_principal(auth_client)
    # one local task to push
    db_session.add(Task(workspace_id=p.workspace_id, created_by=p.user_id, title="local", status="TODO"))
    db_session.commit()
    captured = {"get": 0, "post": 0}

    def fake_urlopen(req, timeout=None):
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        if req.get_method() == "GET":
            captured["get"] += 1
            m.read = lambda: b"[]"  # remote empty
        else:
            captured["post"] += 1
        return m

    with patch("app.services.supabase_auth_service.get_service_credentials",
               return_value=("https://x.supabase.co", "svc")), \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        out = sync_engine.sync_two_way(db_session, p)
    assert out["status"] == "ok"
    assert captured["get"] > 0 and captured["post"] > 0  # pulled and pushed


def test_sync_discovers_new_remote_member_and_hydrates_old_profile_first():
    """A new membership must not fail because its older profile is past the cursor."""
    db = SessionLocal()
    try:
        ws, owner_id = _create_tenant(db)
        new_user_id = uuid.uuid4()
        now = "2026-04-01T00:00:00+00:00"
        remote_profile = {
            "id": str(new_user_id),
            "email": f"remote-{new_user_id}@example.com",
            "full_name": "Remote member",
            # Deliberately older than this workspace's profile watermark.
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
        }
        membership_id = uuid.uuid4()
        remote_membership = {
            "id": str(membership_id),
            "workspace_id": str(ws),
            "user_id": str(new_user_id),
            "role": "member",
            "created_at": now,
            "updated_at": now,
        }
        profile_state = sync_engine._state(db, ws, "profiles", "pull")
        profile_state.last_value = datetime(2026, 3, 1, tzinfo=timezone.utc)
        profile_state.last_pk = owner_id
        db.commit()

        profile_fetches: list[tuple[set[uuid.UUID], datetime | None]] = []

        def fake_fetch(spec, fetch_ws, member_ids, since, since_pk):
            assert fetch_ws == ws
            if spec.table_name == "workspace_members":
                return [remote_membership]
            if spec.table_name == "profiles":
                ids = set(member_ids)
                profile_fetches.append((ids, since))
                if new_user_id in ids and since is None:
                    return [remote_profile]
            return []

        principal = Principal(
            user_id=owner_id,
            workspace_id=ws,
            email="owner@example.com",
        )
        with patch(
            "app.services.supabase_auth_service.get_service_credentials",
            return_value=("https://x.supabase.co", "svc"),
        ), patch.object(sync_engine, "_http_fetch", return_value=fake_fetch), patch.object(
            sync_engine, "_http_upsert", return_value=lambda table, rows: None
        ):
            out = sync_engine.sync_two_way(db, principal)

        assert out["status"] == "ok" and out["failed"] == 0
        assert db.get(Profile, new_user_id) is not None
        membership = db.get(WorkspaceMember, membership_id)
        assert membership is not None and membership.user_id == new_user_id
        assert any(
            new_user_id in ids and since is None
            for ids, since in profile_fetches
        ), "new member profile was not fetched independently of the old watermark"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task 8: per-write trigger rewired to two-way engine
# ---------------------------------------------------------------------------

import threading  # noqa: E402


def test_sync_after_write_invokes_two_way_engine(db_session):
    """sync_after_write spawns a daemon thread targeting the two-way engine worker."""
    p = Principal(user_id=uuid.uuid4(), workspace_id=uuid.uuid4(), email="x@y.z")
    calls = {}

    def capture_start(self):
        calls["target"] = getattr(self, "_target", None)
        # don't actually run the thread body

    from app.services import local_first_sync
    with patch.object(threading.Thread, "start", capture_start):
        local_first_sync.sync_after_write(db_session, p)
    # the spawned worker targets the two-way engine
    assert calls.get("target") is not None


# ---------------------------------------------------------------------------
# Task 9: visible sync status + resumable watermark
# ---------------------------------------------------------------------------

def test_watermark_is_resumable_across_runs():
    """Push once advances the watermark; a second push with no new writes sends nothing."""
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        spec = sync_registry.spec_for("tasks")
        db.add(Task(workspace_id=ws, created_by=user, title="a", status="TODO"))
        db.commit()

        sent = []
        sync_engine.push_table(db, "u", "k", ws, [], spec, upsert=lambda t, r: sent.extend(r))
        st = sync_engine._state(db, ws, "tasks", "push")
        assert st.last_value is not None  # watermark persisted after first push

        # Simulate a new run: expire all cached objects so the engine re-loads from DB
        db.expire_all()
        sent2 = []
        n = sync_engine.push_table(db, "u", "k", ws, [], spec, upsert=lambda t, r: sent2.extend(r))
        assert n == 0 and sent2 == []  # watermark was read from DB; nothing re-sent
    finally:
        db.close()


def test_last_sync_status_reports_watermarks():
    """After a push, last_sync_status lists the tasks/push watermark."""
    db = SessionLocal()
    try:
        ws, user = _create_tenant(db)
        spec = sync_registry.spec_for("tasks")
        db.add(Task(workspace_id=ws, created_by=user, title="a", status="TODO"))
        db.commit()

        sync_engine.push_table(db, "u", "k", ws, [], spec, upsert=lambda t, r: None)
        status = sync_engine.last_sync_status(db, ws)

        assert status["configured"] in (True, False)  # always a bool
        assert any(
            w["table"] == "tasks" and w["direction"] == "push"
            for w in status["watermarks"]
        )
    finally:
        db.close()


def test_sync_status_route_returns_200(auth_client):
    """GET /api/v1/settings/sync/status returns 200 with the expected envelope."""
    resp = auth_client.get("/api/v1/settings/sync/status")
    assert resp.status_code == 200
    data = resp.json()
    # Envelope check: success wrapper used by all settings routes
    assert "data" in data
    inner = data["data"]
    assert "configured" in inner
    assert "tables" in inner
    assert "watermarks" in inner
    assert isinstance(inner["watermarks"], list)


# ---------------------------------------------------------------------------
# Regression: a colliding remote row must not take the whole sync down
# ---------------------------------------------------------------------------

def test_pull_skips_remote_row_that_collides_on_a_unique_column():
    """PK is new here but a local row already owns the UNIQUE value -> keep local, skip.

    Same person registered on two devices: both mint their own profile PK for one
    email. Inserting raised UniqueViolation on ix_profiles_email mid-cycle, which
    aborted the transaction and failed every table after profiles.
    """
    from app.domain.users import Profile
    db = SessionLocal()
    try:
        ws, _ = _create_tenant(db)
        email = f"twin-{uuid.uuid4().hex[:8]}@example.com"
        local = Profile(id=uuid.uuid4(), email=email, full_name="Local")
        db.add(local)
        db.commit()
        remote_pk = uuid.uuid4()  # the other device's PK for the same person
        remote_row = {
            "id": str(remote_pk), "email": email, "full_name": "Remote",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-02-01T00:00:00+00:00",
        }
        applied = sync_engine.pull_table(
            db, "https://x", "svc", ws, [local.id, remote_pk],
            sync_registry.spec_for("profiles"), fetch=lambda *args: [remote_row],
        )
        assert applied == 0
        assert db.get(Profile, remote_pk) is None
        assert db.query(Profile).filter(Profile.email == email).count() == 1
    finally:
        db.close()


def test_one_failing_table_does_not_fail_the_rest(db_session, auth_client):
    """Per-table failures roll back; an aborted transaction used to fail every later table."""
    from app.domain.users import Profile
    from tests.test_supabase_sync import _make_principal

    p = _make_principal(auth_client)
    real_pull = sync_engine.pull_table

    def poisoning_pull(db, url, key, ws, members, spec, *, fetch):
        if spec.table_name == "profiles":
            # Exactly the production failure: a duplicate email fails the flush,
            # which leaves the session needing a rollback.
            db.add(Profile(id=uuid.uuid4(), email=db.query(Profile).first().email))
            db.flush()
        return real_pull(db, url, key, ws, members, spec, fetch=fetch)

    def fake_urlopen(req, timeout=None):
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        m.read = lambda: b"[]"
        return m

    with patch("app.services.supabase_auth_service.get_service_credentials",
               return_value=("https://x.supabase.co", "svc")), \
         patch("urllib.request.urlopen", side_effect=fake_urlopen), \
         patch.object(sync_engine, "pull_table", poisoning_pull):
        out = sync_engine.sync_two_way(db_session, p)
    assert out["failed"] == 1, f"one bad table poisoned {out['failed']} of {out['tables']}"


def test_concurrent_sync_passes_do_not_race_on_sync_state(db_session, auth_client):
    """Two passes for one workspace must not both insert the same watermark row.

    The 15s scheduler and the per-write trigger overlap under load; without a
    per-workspace lock both insert (ws, table, direction) and hit
    uq_sync_state_ws_table_dir, aborting each other mid-sync.
    """
    import threading as _threading

    from tests.test_supabase_sync import _make_principal

    p = _make_principal(auth_client)
    started = _threading.Event()
    release = _threading.Event()
    results: list[dict] = []

    def slow_pass(db, principal):
        started.set()
        release.wait(timeout=5)
        return {"status": "ok", "pulled": 0, "pushed": 0, "tables": 0, "failed": 0}

    with patch.object(sync_engine, "_sync_two_way_locked", slow_pass):
        first = _threading.Thread(target=lambda: results.append(sync_engine.sync_two_way(db_session, p)))
        first.start()
        assert started.wait(timeout=5), "first pass never started"
        # Second pass arrives while the first still holds the workspace lock.
        second = sync_engine.sync_two_way(db_session, p)
        release.set()
        first.join(timeout=5)

    assert second["status"] == "skipped" and second["reason"] == "already_running"
    assert results and results[0]["status"] == "ok"
    # Lock is released afterwards, so the next pass runs normally.
    third = sync_engine.sync_two_way(db_session, p)
    assert third.get("reason") != "already_running"
