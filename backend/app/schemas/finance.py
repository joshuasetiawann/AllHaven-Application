"""Finance schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.domain.finance import CATEGORY_TYPES, DEFAULT_CURRENCY, TRANSACTION_TYPES
from app.schemas.common import ORMModel


def _validate_type(value: str, allowed) -> str:
    value = value.upper()
    if value not in allowed:
        raise ValueError(f"type must be one of {allowed}")
    return value


# --- Categories ---


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        return _validate_type(v, CATEGORY_TYPES)


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        return _validate_type(v, CATEGORY_TYPES) if v is not None else v


class CategoryOut(ORMModel):
    id: uuid.UUID
    name: str
    type: str
    created_at: datetime


# --- Transactions ---


class TransactionCreate(BaseModel):
    type: str
    amount: float = Field(gt=0)
    currency: str = DEFAULT_CURRENCY
    category_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    transaction_date: date

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        return _validate_type(v, TRANSACTION_TYPES)

    @field_validator("currency")
    @classmethod
    def _currency(cls, v):
        v = (v or DEFAULT_CURRENCY).strip().upper()
        return v[:3] if v else DEFAULT_CURRENCY


class TransactionUpdate(BaseModel):
    type: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    transaction_date: Optional[date] = None

    @field_validator("type")
    @classmethod
    def _type(cls, v):
        return _validate_type(v, TRANSACTION_TYPES) if v is not None else v


class TransactionOut(ORMModel):
    id: uuid.UUID
    type: str
    amount: float
    currency: str
    category_id: Optional[uuid.UUID] = None
    category_name_snapshot: Optional[str] = None
    description: Optional[str] = None
    transaction_date: date
    created_at: datetime
    updated_at: datetime


class SummaryOut(BaseModel):
    year: int
    month: int
    currency: str
    total_income: float
    total_expense: float
    balance: float
    transaction_count: int
