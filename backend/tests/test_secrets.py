"""Regression tests for versioned secret encryption and key rotation."""

import base64
import hashlib
import hmac
import os
import struct
import uuid

import pytest

from app.core.config import settings
from app.core.secrets import (
    decrypt_secret,
    encrypt_secret,
    reencrypt_secret,
    secret_needs_reencryption,
)
from app.domain.integrations import IntegrationConfig
from app.domain.users import Profile
from app.domain.workspaces import Workspace
from app.services.secret_rotation_service import rotate_saved_secrets


def _legacy_token(plaintext: str, secret: str) -> str:
    master = hashlib.sha256(secret.encode()).digest()
    enc_key = hashlib.sha256(b"coreos-enc\x00" + master).digest()
    mac_key = hashlib.sha256(b"coreos-mac\x00" + master).digest()
    nonce = os.urandom(16)
    data = plaintext.encode()
    stream = bytearray()
    counter = 0
    while len(stream) < len(data):
        stream.extend(hashlib.sha256(enc_key + nonce + struct.pack(">I", counter)).digest())
        counter += 1
    ciphertext = bytes(a ^ b for a, b in zip(data, stream))
    mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    return base64.b64encode(nonce + mac + ciphertext).decode()


def test_new_secret_uses_randomized_aes_gcm_envelope(monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", "a" * 48)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    first = encrypt_secret("provider-secret")
    second = encrypt_secret("provider-secret")
    assert first.startswith("v3:")
    assert first != second
    assert decrypt_secret(first) == "provider-secret"
    assert not secret_needs_reencryption(first)


def test_tampered_aes_gcm_envelope_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", "b" * 48)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    token = encrypt_secret("do-not-leak")
    raw = bytearray(base64.urlsafe_b64decode(token[3:]))
    raw[-1] ^= 1
    tampered = "v3:" + base64.urlsafe_b64encode(raw).decode()
    with pytest.raises(ValueError, match="integrity"):
        decrypt_secret(tampered)


def test_previous_key_decrypts_and_rotates_forward(monkeypatch):
    old_key = "old-" + "c" * 44
    new_key = "new-" + "d" * 44
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", old_key)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    old_token = encrypt_secret("rotate-me")

    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", new_key)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", old_key)
    assert decrypt_secret(old_token) == "rotate-me"
    assert secret_needs_reencryption(old_token)
    new_token = reencrypt_secret(old_token)
    assert new_token.startswith("v3:") and new_token != old_token

    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    assert decrypt_secret(new_token) == "rotate-me"
    with pytest.raises(ValueError):
        decrypt_secret(old_token)


def test_legacy_envelope_is_read_and_migrated(monkeypatch):
    key = "e" * 48
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", key)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    legacy = _legacy_token("legacy-secret", key)
    assert decrypt_secret(legacy) == "legacy-secret"
    assert secret_needs_reencryption(legacy)
    upgraded = reencrypt_secret(legacy)
    assert upgraded.startswith("v3:")
    assert decrypt_secret(upgraded) == "legacy-secret"


def test_context_binding_rejects_cross_field_ciphertext_swap(monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", "f" * 48)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    token = encrypt_secret("row-specific", context="integration_configs:row-a:api_key")
    assert (
        decrypt_secret(token, context="integration_configs:row-a:api_key")
        == "row-specific"
    )
    with pytest.raises(ValueError, match="integrity"):
        decrypt_secret(token, context="integration_configs:row-a:refresh_token")
    with pytest.raises(ValueError, match="integrity"):
        decrypt_secret(token, context="integration_configs:row-b:api_key")


def test_repeatable_rotation_command_rewrites_previous_key(db_session, monkeypatch):
    old_key = "old-" + "g" * 44
    new_key = "new-" + "h" * 44
    profile = Profile(id=uuid.uuid4(), email="rotate@example.com")
    workspace = Workspace(id=uuid.uuid4(), name="Rotate", owner_id=profile.id)
    row_id = uuid.uuid4()
    context = f"integration_configs:{row_id}:api_key"
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", old_key)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    old_token = encrypt_secret("secret", context=context)

    db_session.add(profile)
    db_session.commit()
    db_session.add(workspace)
    db_session.commit()
    db_session.add(
        IntegrationConfig(
            id=row_id,
            workspace_id=workspace.id,
            provider_id="test",
            provider_type="test",
            display_name="Test",
            created_by=profile.id,
            public_config={},
            encrypted_secrets={"api_key": old_token},
        )
    )
    db_session.commit()

    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY", new_key)
    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", old_key)
    result = rotate_saved_secrets(db_session)
    assert result == {"scanned": 1, "rotated": 1, "rows_changed": 1}
    db_session.expire_all()
    rotated = db_session.get(IntegrationConfig, row_id).encrypted_secrets["api_key"]
    assert rotated != old_token

    monkeypatch.setattr(settings, "SETTINGS_ENCRYPTION_KEY_PREVIOUS", "")
    assert decrypt_secret(rotated, context=context) == "secret"
    assert rotate_saved_secrets(db_session)["rotated"] == 0
