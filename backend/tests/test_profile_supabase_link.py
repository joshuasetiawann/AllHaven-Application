"""Profile carries a nullable supabase_user_id mapping column."""
from __future__ import annotations

from sqlalchemy import inspect

from app.core.database import engine


def test_profile_has_supabase_user_id():
    cols = {c["name"]: c for c in inspect(engine).get_columns("profiles")}
    assert "supabase_user_id" in cols
    assert cols["supabase_user_id"]["nullable"] is True
