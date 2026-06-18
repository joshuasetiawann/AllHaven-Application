# backend/tests/test_migration_revision_ids.py
"""Every Alembic revision id must fit Alembic's default version_num VARCHAR(32).

Regression guard: revision 0015 originally shipped as
``0015_workspace_members_rls_hardening`` (36 chars). Alembic stamps the id into
``alembic_version.version_num`` (VARCHAR(32)); since ``alembic upgrade head``
runs all pending steps in one transaction, the overflow on the final stamp
rolled back the ENTIRE 0010..0015 batch — so columns like
``profiles.supabase_user_id`` were never created and the app 500'd after a
fresh install. Keep revision ids short; the descriptive filename may be longer.
"""
from __future__ import annotations

import re
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
MAX_LEN = 32  # Alembic default alembic_version.version_num is VARCHAR(32)
_REVISION_RE = re.compile(r"""^revision(?::\s*str)?\s*=\s*["']([^"']+)["']""", re.M)


def _revision_ids() -> list[tuple[str, str]]:
    ids: list[tuple[str, str]] = []
    for path in sorted(VERSIONS_DIR.glob("[0-9]*.py")):
        match = _REVISION_RE.search(path.read_text(encoding="utf-8"))
        assert match, f"{path.name}: could not find a top-level `revision = ...`"
        ids.append((path.name, match.group(1)))
    return ids


def test_revision_ids_fit_alembic_version_num():
    too_long = [
        (name, rev, len(rev)) for name, rev in _revision_ids() if len(rev) > MAX_LEN
    ]
    assert not too_long, (
        "Alembic revision ids exceed VARCHAR(32) and will break `upgrade head`: "
        + ", ".join(f"{name} -> {rev!r} ({n} chars)" for name, rev, n in too_long)
    )


def test_revision_ids_are_unique():
    revs = [rev for _, rev in _revision_ids()]
    dupes = {r for r in revs if revs.count(r) > 1}
    assert not dupes, f"duplicate Alembic revision ids: {sorted(dupes)}"
