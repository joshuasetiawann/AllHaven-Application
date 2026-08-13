"""Persistent, exact-token revocation for local and Supabase bearer auth."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.sessions import BearerTokenRevocation

# A remotely verified token should normally carry ``exp``.  If a provider ever
# returns an opaque/malformed-but-valid credential, retaining its digest for 30
# days is safer than silently making logout a no-op and remains storage-bounded.
_FALLBACK_REVOCATION_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_expiry(token: str) -> datetime:
    """Read an already-authenticated JWT's expiry for retention only.

    This is deliberately *not* validation; callers authenticate the credential
    first.  A missing/invalid claim merely selects a conservative retention
    period and can never make an invalid token valid.
    """
    try:
        payload_segment = token.split(".", 2)[1]
        padding = "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_segment + padding))
        expiry = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        if expiry > _now():
            return expiry
    except (IndexError, KeyError, OSError, OverflowError, TypeError, ValueError):
        pass
    return _now() + timedelta(days=_FALLBACK_REVOCATION_DAYS)


def is_revoked(db: Session, token: str) -> bool:
    """Return whether this exact credential has a live deny-list entry."""
    if not token:
        return False
    return db.scalar(
        select(BearerTokenRevocation.id).where(
            BearerTokenRevocation.token_hash == _hash_token(token),
            BearerTokenRevocation.expires_at > _now(),
        )
    ) is not None


def revoke(db: Session, token: str) -> None:
    """Idempotently persist revocation without ever storing the raw token."""
    if not token:
        return

    now = _now()
    db.execute(
        delete(BearerTokenRevocation).where(BearerTokenRevocation.expires_at <= now)
    )
    values = {
        "token_hash": _hash_token(token),
        "expires_at": _token_expiry(token),
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(BearerTokenRevocation).values(**values)
        statement = statement.on_conflict_do_nothing(index_elements=["token_hash"])
    elif dialect == "sqlite":
        statement = sqlite_insert(BearerTokenRevocation).values(**values)
        statement = statement.on_conflict_do_nothing(index_elements=["token_hash"])
    else:  # pragma: no cover - supported deployments are PostgreSQL/SQLite
        existing = db.scalar(
            select(BearerTokenRevocation.id).where(
                BearerTokenRevocation.token_hash == values["token_hash"]
            )
        )
        if existing is not None:
            return
        db.add(BearerTokenRevocation(**values))
        return
    db.execute(statement)
