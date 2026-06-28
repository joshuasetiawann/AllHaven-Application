"""Background two-way Supabase sync scheduler."""
from __future__ import annotations

from app.services import sync_scheduler


def test_start_disabled_is_noop():
    # interval <= 0 must not create a task (used in tests + when sync is off).
    sync_scheduler.start(0)
    assert sync_scheduler._task is None


def test_sync_all_workspaces_no_workspaces_is_safe(_reset_database):
    # Fresh DB has no workspaces: the pass should enumerate nothing and return
    # cleanly (no raise), exercising the session + query path.
    sync_scheduler._sync_all_workspaces()


def test_sync_all_workspaces_skips_when_no_credentials(auth_client, db_session):
    # A registered user has a workspace, but with no Supabase creds configured
    # sync_two_way returns "skipped" — the pass must still complete without error.
    sync_scheduler._sync_all_workspaces()
