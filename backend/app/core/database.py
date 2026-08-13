"""Database engine and session management (SQLAlchemy 2.x).

PostgreSQL is the target database for development and production. The engine
factory also supports SQLite so the automated test suite can run against a fast
in-memory database without external services. Production code paths always use
PostgreSQL via ``DATABASE_URL``.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def make_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine with sensible defaults for the given URL."""
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        connect_args = {"check_same_thread": False}
        if ":memory:" in url or url.endswith(":memory:"):
            db_engine = create_engine(
                url,
                future=True,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            db_engine = create_engine(url, future=True, connect_args=connect_args)

        # SQLite disables FK enforcement by default. Tests and supported local
        # tooling must exercise the same fail-closed relationships as Postgres.
        @event.listens_for(db_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

        return db_engine

    return create_engine(url, future=True, pool_pre_ping=True)


engine: Engine = make_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
