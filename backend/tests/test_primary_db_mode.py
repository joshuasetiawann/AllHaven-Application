"""Primary-database mode: local Postgres (mirror to Supabase) vs Supabase cloud.

The mode is derived from DATABASE_URL so the two can never disagree. Two things
hang off it: the mirror must not run when Supabase is already the primary (it would
copy that database onto itself), and the RLS migrations must apply to any Supabase
database — including one reached without the explicit ALLHAVEN_DB_TARGET opt-in.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Settings

_LOCAL = "postgresql+psycopg://allhaven:pw@db:5432/allhaven"
_SUPABASE = "postgresql+psycopg://postgres.abcd:pw@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

_RLS_MIGRATIONS = (
    "0013_supabase_rls.py",
    "0015_workspace_members_rls_hardening.py",
    "0016_provision_me.py",
)


def test_local_postgres_is_primary_and_keeps_mirroring():
    settings = Settings(DATABASE_URL=_LOCAL, SYNC_INTERVAL_SECONDS=15)
    assert settings.primary_db == "local"
    assert settings.sync_interval_seconds == 15


def test_supabase_primary_turns_the_mirror_off():
    """Mirroring a database onto itself is pure churn — 27 tables of it every tick."""
    settings = Settings(DATABASE_URL=_SUPABASE, SYNC_INTERVAL_SECONDS=15)
    assert settings.primary_db == "supabase"
    assert settings.sync_interval_seconds == 0


def _load_guard(filename: str):
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"_mig_{filename[:4]}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._enabled


def _load_migration(filename: str):
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"_mig_full_{filename[:4]}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rls_migrations_apply_to_a_supabase_url_without_the_explicit_flag(monkeypatch):
    """Otherwise a Supabase-primary install skips RLS and the anon key reads everything."""
    monkeypatch.delenv("ALLHAVEN_DB_TARGET", raising=False)
    for filename in _RLS_MIGRATIONS:
        enabled = _load_guard(filename)
        monkeypatch.setenv("DATABASE_URL", _SUPABASE)
        assert enabled() is True, filename
        monkeypatch.setenv("DATABASE_URL", _LOCAL)
        assert enabled() is False, filename


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _MigrationBind:
    def __init__(self, dialect: str, auth_users: bool):
        self.dialect = SimpleNamespace(name=dialect)
        self.auth_users = auth_users

    def execute(self, _statement):
        return _ScalarResult(self.auth_users)


def test_reconciliation_migration_detects_the_actual_supabase_bind(monkeypatch):
    migration = _load_migration("0023_supabase_security_reconcile.py")
    monkeypatch.delenv("ALLHAVEN_DB_TARGET", raising=False)
    monkeypatch.setenv("DATABASE_URL", _LOCAL)  # deliberately misleading process config
    monkeypatch.setattr(
        migration.op, "get_bind", lambda: _MigrationBind("postgresql", True)
    )

    assert migration._is_supabase_target() is True
    assert "integration_configs" in migration._DENY_TABLES
    assert "ai_agent_configs" in migration._DENY_TABLES
    assert "integration_configs" not in migration._WORKSPACE_TABLES


def test_explicit_supabase_target_fails_closed_on_the_wrong_database(monkeypatch):
    migration = _load_migration("0023_supabase_security_reconcile.py")
    monkeypatch.setenv("ALLHAVEN_DB_TARGET", "supabase")
    monkeypatch.setattr(
        migration.op, "get_bind", lambda: _MigrationBind("postgresql", False)
    )
    with pytest.raises(RuntimeError, match="auth.users"):
        migration._is_supabase_target()
