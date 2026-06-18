"""Local-first write helpers.

All module writes commit to the local database first. When Supabase is enabled,
we start a best-effort background mirror afterwards. Sync failures never block
the user's write path.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.principal import Principal


def sync_after_write(db: Session, principal: Principal) -> None:
    try:
        from app.services import supabase_sync_service

        supabase_sync_service.sync_if_configured(db, principal)
    except Exception:
        # Sync is intentionally non-critical. The local DB is source of truth.
        return
