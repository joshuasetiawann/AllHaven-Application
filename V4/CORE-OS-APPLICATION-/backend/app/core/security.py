"""Security primitives: password hashing and JWT, implemented with the stdlib.

Why stdlib instead of passlib/python-jose:
    Local MVP environments frequently hit native-build or version-conflict issues
    with bcrypt/jose. To keep the one-shot build reliable, password hashing uses
    PBKDF2-HMAC-SHA256 and tokens use a minimal HS256 JWT — both from the Python
    standard library. This is isolated behind the auth boundary and is documented
    as replaceable by bcrypt / Supabase Auth in production (see SECURITY_MODEL.md).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional

from app.core.config import settings

# --- Password hashing (PBKDF2-HMAC-SHA256) ---------------------------------

_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    """Hash a plaintext password into a self-describing, storable string."""
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "$".join(
        [
            _PBKDF2_ALGORITHM,
            str(_PBKDF2_ROUNDS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against a stored hash (constant-time)."""
    try:
        algorithm, rounds_str, salt_b64, hash_b64 = stored.split("$")
        if algorithm != _PBKDF2_ALGORITHM:
            return False
        rounds = int(rounds_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(candidate, expected)


# --- JWT (HS256) -----------------------------------------------------------


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _sign(signing_input: bytes) -> bytes:
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()


def create_access_token(
    subject: str,
    extra_claims: Optional[dict] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """Create a signed HS256 JWT for the given subject (user id)."""
    issued_at = int(time.time())
    expires_at = issued_at + (expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {"sub": subject, "iat": issued_at, "exp": expires_at}
    if extra_claims:
        payload.update(extra_claims)

    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature_segment = _b64url_encode(_sign(signing_input))
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_access_token(token: str) -> dict:
    """Decode and verify an HS256 JWT. Returns the payload or raises ValueError."""
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = _b64url_encode(_sign(signing_input))
    if not hmac.compare_digest(expected_signature, signature_segment):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_segment))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    return payload
