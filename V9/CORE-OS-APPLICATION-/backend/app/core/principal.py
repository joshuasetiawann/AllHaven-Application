"""Authenticated request principal.

A lightweight, immutable view of who is making the request and which workspace
they operate in. Services accept this instead of raw ORM users so workspace
scoping is explicit and the client can never supply its own ``workspace_id``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    full_name: Optional[str] = None
