"""Finance router (thin: delegates to finance_service)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_principal
from app.core.database import get_db
from app.core.principal import Principal
from app.core.responses import success_response
from app.schemas.finance import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    SummaryOut,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from app.services import finance_service

router = APIRouter(prefix="/finance", tags=["finance"])

# --- Categories ---


@router.get("/categories")
def list_categories(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    categories = finance_service.list_categories(db, principal)
    return success_response(
        [CategoryOut.model_validate(c) for c in categories], "Categories retrieved"
    )


@router.post("/categories")
def create_category(
    payload: CategoryCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    category = finance_service.create_category(db, principal, payload)
    return success_response(CategoryOut.model_validate(category), "Category created")


@router.patch("/categories/{category_id}")
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    category = finance_service.update_category(db, principal, category_id, payload)
    return success_response(CategoryOut.model_validate(category), "Category updated")


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    finance_service.delete_category(db, principal, category_id)
    return success_response({"id": str(category_id)}, "Category deleted")


# --- Transactions ---


@router.get("/transactions")
def list_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    transactions = finance_service.list_transactions(db, principal, limit=limit, offset=offset)
    return success_response(
        [TransactionOut.model_validate(t) for t in transactions], "Transactions retrieved"
    )


@router.post("/transactions")
def create_transaction(
    payload: TransactionCreate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    transaction = finance_service.create_transaction(db, principal, payload)
    return success_response(TransactionOut.model_validate(transaction), "Transaction created")


@router.get("/transactions/{transaction_id}")
def get_transaction(
    transaction_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    transaction = finance_service.get_transaction(db, principal, transaction_id)
    return success_response(TransactionOut.model_validate(transaction), "Transaction retrieved")


@router.patch("/transactions/{transaction_id}")
def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    transaction = finance_service.update_transaction(db, principal, transaction_id, payload)
    return success_response(TransactionOut.model_validate(transaction), "Transaction updated")


@router.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    finance_service.delete_transaction(db, principal, transaction_id)
    return success_response({"id": str(transaction_id)}, "Transaction deleted")


# --- Summary ---


@router.get("/summary")
def summary(
    year: int = Query(default=date.today().year, ge=2000, le=2100),
    month: int = Query(default=date.today().month, ge=1, le=12),
    currency: str = Query(default="IDR"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    result = finance_service.monthly_summary(
        db, principal, year=year, month=month, currency=currency.upper()
    )
    return success_response(SummaryOut(**result), "Monthly summary")
