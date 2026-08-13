"""Regression tests for the additive security-reconciliation migrations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _load_migration(filename: str):
    path = VERSIONS_DIR / filename
    module_name = f"_migration_test_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves postponed annotations through sys.modules.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _SupabaseBind:
    dialect = SimpleNamespace(name="postgresql")

    def execute(self, _statement):
        return _ScalarResult(True)


def test_0023_replaces_the_complete_prior_policy_set(monkeypatch):
    migration = _load_migration("0023_supabase_security_reconcile.py")
    statements: list[str] = []
    monkeypatch.delenv("ALLHAVEN_DB_TARGET", raising=False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: _SupabaseBind())
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    policy_tables = [
        *migration._WORKSPACE_TABLES,
        "profiles",
        "workspaces",
        "workspace_members",
        "audit_logs",
        *migration._DENY_TABLES,
    ]
    for table in policy_tables:
        cleanup_indexes = [
            index
            for index, sql in enumerate(statements)
            if "FROM pg_policies" in sql and f"tablename = '{table}'" in sql
        ]
        assert len(cleanup_indexes) == 1, table

        policy_indexes = [
            index
            for index, sql in enumerate(statements)
            if "CREATE POLICY" in sql and f'ON public."{table}"' in sql
        ]
        if table in migration._DENY_TABLES:
            assert policy_indexes == [], table
        else:
            assert cleanup_indexes[0] < min(policy_indexes), table


def test_0023_provisioning_never_claims_an_unlinked_profile_by_email():
    migration = _load_migration("0023_supabase_security_reconcile.py")
    sql = " ".join(migration._PROVISION_FN.split())

    assert "existing profile requires trusted backend linkage" in sql
    assert "UPDATE public.profiles" not in sql
    assert sql.index("IF EXISTS ( SELECT 1 FROM public.profiles") < sql.index(
        "INSERT INTO public.profiles"
    )


def test_0023_downgrade_retains_preexisting_security_objects(monkeypatch):
    migration = _load_migration("0023_supabase_security_reconcile.py")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("reconciliation downgrade must not mutate preexisting objects")

    monkeypatch.setattr(migration.op, "execute", unexpected)
    monkeypatch.setattr(migration.op, "get_bind", unexpected)
    migration.downgrade()


def test_0025_sqlite_normalizes_nullable_cross_tenant_link(monkeypatch):
    migration = _load_migration("0025_tenant_fk_reconcile.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE parents ("
            "id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, "
            "UNIQUE (workspace_id, id))"
        ))
        connection.execute(sa.text(
            "CREATE TABLE children ("
            "id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, parent_id TEXT)"
        ))
        connection.execute(sa.text(
            "INSERT INTO parents (id, workspace_id) VALUES ('parent-b', 'workspace-b')"
        ))
        connection.execute(sa.text(
            "INSERT INTO children (id, workspace_id, parent_id) "
            "VALUES ('child-a', 'workspace-a', 'parent-b')"
        ))

        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        monkeypatch.setattr(migration.op, "execute", connection.execute)
        migration._preflight_link(
            migration.Link("children", "parent_id", "parents", nullable=True)
        )

        assert connection.scalar(sa.text(
            "SELECT parent_id FROM children WHERE id = 'child-a'"
        )) is None


def test_0025_downgrade_does_not_remove_0022_owned_constraints(monkeypatch):
    migration = _load_migration("0025_tenant_fk_reconcile.py")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("repair downgrade must not drop provenance-ambiguous constraints")

    monkeypatch.setattr(migration.op, "get_bind", unexpected)
    monkeypatch.setattr(migration.op, "drop_constraint", unexpected)
    monkeypatch.setattr(migration.op, "batch_alter_table", unexpected)
    migration.downgrade()


def test_0026_repeats_policy_cleanup_at_a_new_head(monkeypatch):
    migration = _load_migration("0026_security_closure_reconcile.py")
    statements: list[str] = []
    monkeypatch.delenv("ALLHAVEN_DB_TARGET", raising=False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: _SupabaseBind())
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    assert migration.down_revision == "0025_tenant_fk_reconcile"
    for table in [
        *migration._WORKSPACE_TABLES,
        "profiles",
        "workspaces",
        "workspace_members",
        "audit_logs",
        *migration._DENY_TABLES,
    ]:
        assert sum(
            "FROM pg_policies" in sql and f"tablename = '{table}'" in sql
            for sql in statements
        ) == 1, table
    provision_sql = " ".join(migration._PROVISION_FN.split())
    assert "existing profile requires trusted backend linkage" in provision_sql
    assert "UPDATE public.profiles" not in provision_sql


def test_0026_resets_every_recreated_function_owner_to_the_migration_role():
    migration = _load_migration("0026_security_closure_reconcile.py")

    helper_sql = " ".join(migration._HELPERS.split())
    provision_sql = " ".join(migration._PROVISION_FN.split())

    expected = [
        (helper_sql, "public.app_user_id()", "public.app_user_id()"),
        (helper_sql, "public.is_member(ws uuid)", "public.is_member(uuid)"),
        (
            provision_sql,
            "public.provision_me(p_full_name text DEFAULT NULL)",
            "public.provision_me(text)",
        ),
    ]
    for sql, declaration, signature in expected:
        create = f"CREATE OR REPLACE FUNCTION {declaration}"
        reset_owner = f"ALTER FUNCTION {signature} OWNER TO CURRENT_USER"
        revoke = f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC"

        assert sql.count(create) == 1
        assert sql.count(reset_owner) == 1
        assert sql.index(create) < sql.index(reset_owner) < sql.index(revoke)


def test_0026_downgrade_retains_hardened_objects(monkeypatch):
    migration = _load_migration("0026_security_closure_reconcile.py")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("security reconciliation downgrade must be additive")

    monkeypatch.setattr(migration.op, "execute", unexpected)
    monkeypatch.setattr(migration.op, "get_bind", unexpected)
    migration.downgrade()


def test_0027_reconciles_preexisting_function_owners_at_a_new_head(monkeypatch):
    migration = _load_migration("0027_function_owner_reconcile.py")
    statements: list[str] = []
    monkeypatch.delenv("ALLHAVEN_DB_TARGET", raising=False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: _SupabaseBind())
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    assert migration.down_revision == "0026_security_closure"
    assert statements == [
        f"ALTER FUNCTION {signature} OWNER TO CURRENT_USER;"
        for signature in migration._FUNCTION_SIGNATURES
    ]


def test_0027_downgrade_never_restores_an_untrusted_owner(monkeypatch):
    migration = _load_migration("0027_function_owner_reconcile.py")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("ownership reconciliation must remain in place")

    monkeypatch.setattr(migration.op, "execute", unexpected)
    monkeypatch.setattr(migration.op, "get_bind", unexpected)
    migration.downgrade()


def test_0029_collision_audit_fails_before_creating_indexes(monkeypatch):
    migration = _load_migration("0029_case_insensitive_email_unique.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE local_users (email TEXT NOT NULL)"))
        connection.execute(sa.text("CREATE TABLE profiles (email TEXT NOT NULL)"))
        connection.execute(sa.text(
            "INSERT INTO local_users (email) VALUES ('Twin@Example.com'), ('twin@example.COM')"
        ))
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        created: list[str] = []
        monkeypatch.setattr(
            migration.op,
            "create_index",
            lambda name, *_args, **_kwargs: created.append(name),
        )
        with pytest.raises(RuntimeError, match="collisions") as raised:
            migration.upgrade()
        assert created == []
        assert "Twin" not in str(raised.value)
        assert connection.scalar(sa.text("SELECT count(*) FROM local_users")) == 2


def test_0029_creates_both_case_insensitive_unique_indexes(monkeypatch):
    migration = _load_migration("0029_case_insensitive_email_unique.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE local_users (email TEXT NOT NULL)"))
        connection.execute(sa.text("CREATE TABLE profiles (email TEXT NOT NULL)"))
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        created: list[tuple] = []
        monkeypatch.setattr(
            migration.op,
            "create_index",
            lambda *args, **kwargs: created.append((args, kwargs)),
        )
        migration.upgrade()
        assert migration.down_revision == "0028_bearer_revocations"
        assert [args[0] for args, _kwargs in created] == [
            "uq_local_users_email_ci",
            "uq_profiles_email_ci",
        ]
        assert all(kwargs["unique"] is True for _args, kwargs in created)
