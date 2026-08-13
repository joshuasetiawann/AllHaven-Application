"""Secret storage helpers: versioned authenticated encryption and masking.

New values use AES-256-GCM from PyCA ``cryptography``. The versioned envelope
lets AllHaven rotate keys and migrate the legacy MVP format without losing
already-saved provider credentials.

Security rules enforced here:
    * Plaintext secrets are never returned to the frontend, only masked previews.
    * Secret values are never logged.
    * Previous keys are decryption-only and new writes always use the current key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_V3_PREFIX = "v3:"
_V2_PREFIX = "v2:"
_AEAD_NONCE_BYTES = 12
_AEAD_TAG_BYTES = 16
_V2_AAD = b"allhaven-settings-secret:v2"

# Legacy constants are retained for read-only migration compatibility. New
# ciphertext is never produced with the custom construction.
_LEGACY_NONCE_BYTES = 16
_LEGACY_MAC_BYTES = 32


def _configured_keys() -> list[str]:
    """Current key followed by decryption-only rotation keys."""
    keys = [settings.SETTINGS_ENCRYPTION_KEY]
    previous = (settings.SETTINGS_ENCRYPTION_KEY_PREVIOUS or "").strip()
    if previous:
        keys.extend(part.strip() for part in previous.split(",") if part.strip())
    return list(dict.fromkeys(keys))


def _aead_key(secret: str) -> bytes:
    # Keep the v2 derivation label so existing key material does not fork into
    # two unrelated operator-managed keys. Envelope/AAD versioning separates
    # the formats cryptographically.
    return hashlib.sha256(b"allhaven-aes-gcm-v2\x00" + secret.encode("utf-8")).digest()


def _context_aad(context: str | None) -> bytes:
    """Bind ciphertext to its exact table/row/field storage location."""
    normalized = context if context is not None else "global"
    if not isinstance(normalized, str) or not normalized:
        raise ValueError("Secret encryption context must be a non-empty string")
    encoded = normalized.encode("utf-8")
    if len(encoded) > 1024:
        raise ValueError("Secret encryption context is too long")
    return b"allhaven-settings-secret:v3\x00" + encoded


def _legacy_subkeys(secret: str) -> tuple[bytes, bytes]:
    master = hashlib.sha256(secret.encode("utf-8")).digest()
    # These labels must remain unchanged so pre-v2 values stay decryptable.
    enc_key = hashlib.sha256(b"coreos-enc\x00" + master).digest()
    mac_key = hashlib.sha256(b"coreos-mac\x00" + master).digest()
    return enc_key, mac_key


def _legacy_keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    """Legacy decoder helper; do not use for new encryption."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(enc_key + nonce + struct.pack(">I", counter)).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_secret(plaintext: str, *, context: str | None = None) -> str:
    """Encrypt into a context-bound AES-256-GCM v3 envelope.

    ``context`` should identify the table, row and field. The global default is
    retained only for standalone callers/tests; persisted config paths always
    supply a concrete context.
    """
    nonce = os.urandom(_AEAD_NONCE_BYTES)
    ciphertext = AESGCM(_aead_key(settings.SETTINGS_ENCRYPTION_KEY)).encrypt(
        nonce, plaintext.encode("utf-8"), _context_aad(context)
    )
    return _V3_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decode_aead(token: str, prefix: str, secret: str, aad: bytes) -> str:
    try:
        raw = base64.b64decode(token[len(prefix) :], altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid secret envelope") from exc
    if len(raw) < _AEAD_NONCE_BYTES + _AEAD_TAG_BYTES:
        raise ValueError("Invalid secret envelope")
    nonce, ciphertext = raw[:_AEAD_NONCE_BYTES], raw[_AEAD_NONCE_BYTES:]
    try:
        cleartext = AESGCM(_aead_key(secret)).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise ValueError("Secret integrity check failed") from exc
    try:
        return cleartext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid secret plaintext") from exc


def _decode_v3(token: str, secret: str, context: str | None) -> str:
    return _decode_aead(token, _V3_PREFIX, secret, _context_aad(context))


def _decode_v2(token: str, secret: str) -> str:
    return _decode_aead(token, _V2_PREFIX, secret, _V2_AAD)


def _decode_legacy(token: str, secret: str) -> str:
    try:
        raw = base64.b64decode(token, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid legacy secret envelope") from exc
    if len(raw) < _LEGACY_NONCE_BYTES + _LEGACY_MAC_BYTES:
        raise ValueError("Invalid legacy secret envelope")
    nonce = raw[:_LEGACY_NONCE_BYTES]
    mac = raw[_LEGACY_NONCE_BYTES : _LEGACY_NONCE_BYTES + _LEGACY_MAC_BYTES]
    ciphertext = raw[_LEGACY_NONCE_BYTES + _LEGACY_MAC_BYTES :]
    enc_key, mac_key = _legacy_subkeys(secret)
    expected = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("Secret integrity check failed")
    cleartext = bytes(
        a ^ b
        for a, b in zip(
            ciphertext, _legacy_keystream(enc_key, nonce, len(ciphertext))
        )
    )
    try:
        return cleartext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid secret plaintext") from exc


def decrypt_secret(token: str, *, context: str | None = None) -> str:
    """Decrypt v3, v2, or legacy data using the current/previous key ring."""
    if not isinstance(token, str) or not token:
        raise ValueError("Invalid secret envelope")
    for secret in _configured_keys():
        try:
            if token.startswith(_V3_PREFIX):
                return _decode_v3(token, secret, context)
            if token.startswith(_V2_PREFIX):
                return _decode_v2(token, secret)
            return _decode_legacy(token, secret)
        except ValueError:
            continue
    raise ValueError("Secret integrity check failed")


def secret_needs_reencryption(token: str, *, context: str | None = None) -> bool:
    """Return whether a token needs v3/context/current-key rewriting."""
    if not token.startswith(_V3_PREFIX):
        decrypt_secret(token, context=context)
        return True
    try:
        _decode_v3(token, settings.SETTINGS_ENCRYPTION_KEY, context)
        return False
    except ValueError:
        # A previous key is acceptable for reading, but must be rotated forward.
        decrypt_secret(token, context=context)
        return True


def reencrypt_secret(token: str, *, context: str | None = None) -> str:
    """Upgrade legacy/v2/previous-key ciphertext to context-bound v3."""
    if not secret_needs_reencryption(token, context=context):
        return token
    return encrypt_secret(decrypt_secret(token, context=context), context=context)


def mask_secret(value: str) -> str:
    """Return a masked preview of a secret, e.g. ``sk-••••abcd``."""
    if not value:
        return ""
    if len(value) <= 6:
        return "••••"
    return f"{value[:3]}••••{value[-4:]}"
