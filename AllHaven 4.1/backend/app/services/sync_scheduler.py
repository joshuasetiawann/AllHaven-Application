"""Background scheduler for the two-way Supabase sync.

The per-write trigger (``local_first_sync.sync_after_write``) only runs the engine
when the DESKTOP writes something. The phone writes straight to Supabase and never
calls this backend, so while the desktop sat idle, phone-side changes were never
pulled and failed desktop pushes were never retried.

This loop runs ``sync_engine.sync_two_way`` for every workspace on a fixed
interval, so both directions converge continuously (and transient failures get
retried on the next tick). It is best-effort: it never raises, and it is a no-op
when Supabase isn't configured (``sync_two_way`` returns ``skipped`` with no creds)
or when ``SYNC_INTERVAL_SECONDS`` is 0.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


def _sync_all_workspaces() -> None:
    """One blocking sync pass over every workspace. Runs in a worker thread.

    A fresh ``SessionLocal`` per workspace mirrors ``local_first_sync._worker`` so a
    failure in one workspace can't leave a shared session in a bad state.
    """
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.principal import Principal
    from app.domain.workspaces import Workspace
    from app.services import sync_engine

    enum_db = SessionLocal()
    try:
        workspaces = enum_db.execute(select(Workspace.id, Workspace.owner_id)).all()
    finally:
        enum_db.close()

    for ws_id, owner_id in workspaces:
        db = SessionLocal()
        try:
            sync_engine.sync_two_way(
                db, Principal(user_id=owner_id, workspace_id=ws_id, email="")
            )
        except Exception as exc:  # per-workspace isolation; never break the loop
            log.debug("scheduled sync failed for workspace %s: %s", ws_id, exc)
        finally:
            db.close()


async def _loop(interval: int) -> None:
    # Let startup finish before the first (potentially slow) sync pass.
    await asyncio.sleep(min(interval, 10))
    while True:
        try:
            await asyncio.to_thread(_sync_all_workspaces)
        except Exception as exc:  # a tick must never kill the loop
            log.debug("sync scheduler tick failed: %s", exc)
        await asyncio.sleep(interval)


_task: "asyncio.Task | None" = None


def start(interval: int) -> None:
    """Start the periodic sync loop (idempotent). interval<=0 disables it."""
    global _task
    if interval <= 0 or _task is not None:
        return
    _task = asyncio.create_task(_loop(interval))
    log.info("Supabase two-way sync scheduler started (every %ss)", interval)


async def stop() -> None:
    """Cancel the loop on shutdown."""
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    except Exception:  # pragma: no cover - defensive
        pass
    _task = None
