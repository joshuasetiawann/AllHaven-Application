"""Pasting a Supabase connection string must Just Work.

Supabase (like most managed hosts) hands out a driver-less ``postgresql://`` URL,
but only psycopg 3 is installed — SQLAlchemy would default to psycopg2 and die at
import. And ``primary_db`` decides whether the local→Supabase mirror runs at all,
so it has to recognise the pooler hostname, not just ``db.<ref>.supabase.co``.
Both are one-line rules that silently split desktop and phone onto two different
databases when they are wrong.
"""

import pytest

from app.core.config import Settings
from app.core.database import make_engine

POOLER_URL = (
    "postgresql://postgres.abcdefghijklmnop:pw"
    "@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
)
DIRECT_URL = "postgresql://postgres:pw@db.abcdefghijklmnop.supabase.co:5432/postgres"


@pytest.mark.parametrize(
    ("url", "driver"),
    [
        (POOLER_URL, "psycopg"),
        (DIRECT_URL, "psycopg"),
        # Legacy scheme some dashboards still emit.
        ("postgres://u:p@h:5432/d", "psycopg"),
        # An explicit driver is left alone.
        ("postgresql+psycopg://u:p@h:5432/d", "psycopg"),
        ("sqlite:///:memory:", "pysqlite"),
    ],
)
def test_make_engine_pins_the_installed_driver(url: str, driver: str) -> None:
    assert make_engine(url).dialect.driver == driver


@pytest.mark.parametrize("url", [POOLER_URL, DIRECT_URL])
def test_supabase_urls_make_supabase_the_primary_database(url: str) -> None:
    settings = Settings(DATABASE_URL=url)
    assert settings.primary_db == "supabase"
    # Nothing to mirror when Supabase already IS the database.
    assert settings.sync_interval_seconds == 0


def test_a_local_url_keeps_the_mirror_running() -> None:
    settings = Settings(DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/allhaven")
    assert settings.primary_db == "local"
