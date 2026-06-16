"""Secret storage helpers: encryption at rest and masking.

MVP encryption scheme (standard library only — no native deps):
    Encrypt-then-MAC using a SHA-256 keystream in counter mode for confidentiality
    and HMAC-SHA256 for integrity. Keys are derived from SETTINGS_ENCRYPTION_KEY.

    This keeps secrets encrypted at rest for a local MVP without pulling in a
    native crypto dependency. It is clearly documented as replaceable by a vetted
    library (e.g. ``cryptography`` Fernet) or a managed KMS in production.

Security rules enforced here:
    * Plaintext secrets are never returned to the frontend — only masked previews.
    * Secret values are never logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct

from app.core.config import settings

_NONCE_BYTES = 16
_MAC_BYTES = 32


def _master_key() -> bytes:
    return hashlib.sha256(settings.SETTINGS_ENCRYPTION_KEY.encode("utf-8")).digest()


def _subkeys() -> tuple[bytes, bytes]:
    master = _master_key()
    enc_key = hashlib.sha256(b"coreos-enc\x00" + master).digest()
    mac_key = hashlib.sha256(b"coreos-mac\x00" + master).digest()
    return enc_key, mac_key


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(enc_key + nonce + struct.pack(">I", counter)).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string into a self-describing base64 token."""
    enc_key, mac_key = _subkeys()
    nonce = os.urandom(_NONCE_BYTES)
    data = plaintext.encode("utf-8")
    keystream = _keystream(enc_key, nonce, len(data))
    ciphertext = bytes(a ^ b for a, b in zip(data, keystream))
    mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    return base64.b64encode(nonce + mac + ciphertext).decode("ascii")


def decrypt_secret(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt_secret`. Raises on tampering."""
    raw = base64.b64decode(token)
    nonce = raw[:_NONCE_BYTES]
    mac = raw[_NONCE_BYTES : _NONCE_BYTES + _MAC_BYTES]
    ciphertext = raw[_NONCE_BYTES + _MAC_BYTES :]
    enc_key, mac_key = _subkeys()
    expected = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("Secret integrity check failed")
    keystream = _keystream(enc_key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, keystream)).decode("utf-8")


def mask_secret(value: str) -> str:
    """Return a masked preview of a secret, e.g. ``sk-••••abcd``. Never the full value."""
    if not value:
        return ""
    if len(value) <= 6:
        return "••••"
    head = value[:3]
    tail = value[-4:]
    return f"{head}••••{tail}"
