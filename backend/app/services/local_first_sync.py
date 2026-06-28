"""Local-first write helpers.

All module writes commit to the local database first. When Supabase is enabled,
we start a best-effort background incremental two-way sync afterwards. Sync
failures never block the user's write path.

The per-write trigger spawns a daemon thread so that the HTTP round-trips to
Supabase happen entirely off the request path. The thread opens its own
SessionLocal so the caller's session is never shared across threads.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import Session

from app.core.principal import Principal

log = logging.getLogger(__name__)


def _worker(workspace_id, user_id, email) -> None:
    """Background worker: open a fresh session and run the two-way engine."""
    from app.core.database import SessionLocal
    from app.core.principal import Principal
    from app.services import sync_engine

    db = SessionLocal()
    try:
        sync_engine.sync_two_way(
            db,
            Principal(user_id=user_id, workspace_id=workspace_id, email=email),
        )
    except Exception as exc:  # never propagate — best-effort
        log.debug("local_first_sync worker failed: %s", exc)
    finally:
        db.close()


def sync_after_write(db: Session, principal: Principal) -> None:
    """Best-effort: kick an incremental two-way sync in a daemon thread.

    Replaces the old one-way full-table ``supabase_sync_service.sync_if_configured``
    call with an incremental pull-then-push via ``sync_engine.sync_two_way``.
    Signature is unchanged so the ~80 callers require no modifications.

    The caller's ``db`` session is intentionally NOT passed to the thread;
    the thread opens its own SessionLocal to avoid cross-thread session sharing.
    """
    try:
        t = threading.Thread(
            target=_worker,
            args=(principal.workspace_id, principal.user_id, principal.email),
            daemon=True,
        )
        t.start()
    except Exception:
        return
