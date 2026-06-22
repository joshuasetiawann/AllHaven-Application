"""Finance models: categories and transactions.

AllHaven tracks cashflow only. It does not provide financial advice and never moves
money. Amounts are stored as NUMERIC for accuracy. Both tables are soft-deleted.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin

CATEGORY_TYPES = ("INCOME", "EXPENSE")
TRANSACTION_TYPES = ("INCOME", "EXPENSE")
DEFAULT_CURRENCY = "IDR"


class FinanceCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "finance_categories"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default=DEFAULT_CURRENCY)

    category_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    # Snapshot so historical rows keep their category label even if the category changes.
    category_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Cross-device idempotency: an approved proposal stamps "{proposal_id}:{ordinal}"
    # here. A UNIQUE index (NULLs distinct, so manual rows are unaffected) makes the
    # rare pre-sync race — both devices approve before executed_at syncs — converge to
    # ONE row instead of duplicating. See sync_engine.lww_apply + ai_tools_registry.
    dedup_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_transactions_dedup_key", "dedup_key", unique=True),
    )
