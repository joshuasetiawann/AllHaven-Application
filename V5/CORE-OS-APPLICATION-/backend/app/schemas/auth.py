"""Auth schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel, normalize_email


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    created_at: datetime


class WorkspaceOut(ORMModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MeData(BaseModel):
    user: UserOut
    workspace: WorkspaceOut
