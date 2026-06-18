"""Alembic environment.

The database URL and target metadata come from the application itself so the
migration always matches the models and configured database.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

# Import the domain package so every model is registered on Base.metadata.
import app.domain  # noqa: F401
from app.domain.base import Base

config = context.config
# Alembic stores options via configparser, whose interpolation treats `%` as a
# special character — a URL-encoded password (e.g. `%40` for `@`, common in
# Supabase connection strings) would raise "invalid interpolation syntax". Escape
# `%` -> `%%` for storage; the migrations connect using settings.DATABASE_URL
# directly (run_migrations_offline/online below), where SQLAlchemy percent-decodes
# it. No-op for URLs without `%` (the local default).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
