"""Finance service: categories, transactions, and the monthly summary.

AllHaven tracks cashflow only — it never provides financial advice or moves money.
All writes are workspace-scoped, soft-deleted, and audited.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.principal import Principal
from app.domain.finance import FinanceCategory, Transaction
from app.schemas.finance import (
    CategoryCreate,
    CategoryUpdate,
    TransactionCreate,
    TransactionUpdate,
)
from app.services.audit_service import snapshot, write_audit

# --- Categories ---


def list_categories(db: Session, principal: Principal) -> List[FinanceCategory]:
    stmt = (
        select(FinanceCategory)
        .where(
            FinanceCategory.workspace_id == principal.workspace_id,
            FinanceCategory.is_deleted.is_(False),
        )
        .order_by(FinanceCategory.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_category(db: Session, principal: Principal, category_id: uuid.UUID) -> FinanceCategory:
    category = db.scalar(
        select(FinanceCategory).where(
            FinanceCategory.id == category_id,
            FinanceCategory.workspace_id == principal.workspace_id,
            FinanceCategory.is_deleted.is_(False),
        )
    )
    if not category:
        raise NotFoundError("Finance category not found.")
    return category


def create_category(db: Session, principal: Principal, data: CategoryCreate) -> FinanceCategory:
    category = FinanceCategory(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        name=data.name,
        type=data.type,
    )
    db.add(category)
    db.flush()
    write_audit(
        db,
        action="CREATE",
        entity_name="finance_category",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=category.id,
        after=snapshot(category),
    )
    db.commit()
    db.refresh(category)
    return category


def update_category(
    db: Session, principal: Principal, category_id: uuid.UUID, data: CategoryUpdate
) -> FinanceCategory:
    category = get_category(db, principal, category_id)
    before = snapshot(category)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    db.flush()
    write_audit(
        db,
        action="UPDATE",
        entity_name="finance_category",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=category.id,
        before=before,
        after=snapshot(category),
    )
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, principal: Principal, category_id: uuid.UUID) -> None:
    category = get_category(db, principal, category_id)
    before = snapshot(category)
    category.is_deleted = True
    db.flush()
    write_audit(
        db,
        action="DELETE",
        entity_name="finance_category",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=category.id,
        before=before,
    )
    db.commit()


# --- Transactions ---


def _resolve_category_snapshot(
    db: Session, principal: Principal, category_id: Optional[uuid.UUID]
) -> Optional[str]:
    if category_id is None:
        return None
    category = get_category(db, principal, category_id)
    return category.name


def list_transactions(
    db: Session,
    principal: Principal,
    *,
    limit: int = 100,
    offset: int = 0,
    year: Optional[int] = None,
    month: Optional[int] = None,
    currency: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[Transaction]:
    filters = [
        Transaction.workspace_id == principal.workspace_id,
        Transaction.is_deleted.is_(False),
    ]
    if start is not None:
        filters.append(Transaction.transaction_date >= start)
    if end is not None:
        filters.append(Transaction.transaction_date <= end)
    if start is None and end is None and year is not None and month is not None:
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        filters.extend([
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end,
        ])
    if currency:
        filters.append(Transaction.currency == currency.upper())

    stmt = (
        select(Transaction)
        .where(*filters)
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


def get_transaction(db: Session, principal: Principal, transaction_id: uuid.UUID) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.workspace_id == principal.workspace_id,
            Transaction.is_deleted.is_(False),
        )
    )
    if not transaction:
        raise NotFoundError("Transaction not found.")
    return transaction


def create_transaction(
    db: Session, principal: Principal, data: TransactionCreate
) -> Transaction:
    category_name = _resolve_category_snapshot(db, principal, data.category_id)
    transaction = Transaction(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        type=data.type,
        amount=Decimal(str(data.amount)),
        currency=data.currency,
        category_id=data.category_id,
        category_name_snapshot=category_name,
        description=data.description,
        transaction_date=data.transaction_date,
    )
    db.add(transaction)
    db.flush()
    write_audit(
        db,
        action="CREATE",
        entity_name="transaction",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=transaction.id,
        after=snapshot(transaction),
    )
    db.commit()
    db.refresh(transaction)
    return transaction


def update_transaction(
    db: Session, principal: Principal, transaction_id: uuid.UUID, data: TransactionUpdate
) -> Transaction:
    transaction = get_transaction(db, principal, transaction_id)
    before = snapshot(transaction)

    fields = data.model_dump(exclude_unset=True)
    if "amount" in fields and fields["amount"] is not None:
        fields["amount"] = Decimal(str(fields["amount"]))
    if "category_id" in fields:
        transaction.category_name_snapshot = _resolve_category_snapshot(
            db, principal, fields["category_id"]
        )
    for key, value in fields.items():
        setattr(transaction, key, value)
    transaction.updated_by = principal.user_id

    db.flush()
    write_audit(
        db,
        action="UPDATE",
        entity_name="transaction",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=transaction.id,
        before=before,
        after=snapshot(transaction),
    )
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, principal: Principal, transaction_id: uuid.UUID) -> None:
    transaction = get_transaction(db, principal, transaction_id)
    before = snapshot(transaction)
    transaction.is_deleted = True
    transaction.updated_by = principal.user_id
    db.flush()
    write_audit(
        db,
        action="DELETE",
        entity_name="transaction",
        workspace_id=principal.workspace_id,
        user_id=principal.user_id,
        entity_id=transaction.id,
        before=before,
    )
    db.commit()


# --- Summary ---


def monthly_summary(
    db: Session,
    principal: Principal,
    *,
    year: int,
    month: int,
    currency: str = "IDR",
) -> dict:
    """Aggregate income/expense for a given month. No advice, just arithmetic."""
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    result = range_summary(
        db,
        principal,
        start=start,
        end=end,
        currency=currency,
        period_type="month",
    )
    return {
        "year": year,
        "month": month,
        "currency": result["currency"],
        "total_income": result["total_income"],
        "total_expense": result["total_expense"],
        "balance": result["balance"],
        "transaction_count": result["transaction_count"],
    }


def range_summary(
    db: Session,
    principal: Principal,
    *,
    start: date,
    end: date,
    currency: str = "IDR",
    period_type: str = "custom",
) -> dict:
    """Aggregate income/expense for any reporting period."""
    stmt = select(Transaction).where(
        Transaction.workspace_id == principal.workspace_id,
        Transaction.is_deleted.is_(False),
        Transaction.currency == currency,
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
    )
    transactions = list(db.scalars(stmt).all())

    total_income = sum((t.amount for t in transactions if t.type == "INCOME"), Decimal("0"))
    total_expense = sum((t.amount for t in transactions if t.type == "EXPENSE"), Decimal("0"))
    balance = total_income - total_expense

    return {
        "period_type": period_type,
        "start_date": start,
        "end_date": end,
        "currency": currency,
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "balance": float(balance),
        "transaction_count": len(transactions),
    }
