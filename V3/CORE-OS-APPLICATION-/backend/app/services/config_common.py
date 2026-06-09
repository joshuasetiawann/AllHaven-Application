"""Shared helpers for integration & AI-agent config rows.

Centralizes secret encryption/decryption, masked previews, and status logic so
both the integration service and the AI provider router behave identically and
never leak secrets.
"""

from __future__ import annotations

from app.core.secrets import decrypt_secret, encrypt_secret, mask_secret
from app.services.provider_registry import ProviderSpec


def get_secret_value(row, field: str) -> str | None:
    token = (row.encrypted_secrets or {}).get(field)
    if not token:
        return None
    try:
        return decrypt_secret(token)
    except Exception:  # noqa: BLE001 - corrupted/old token: treat as not set
        return None


def decrypt_all(row, secret_fields: list[str]) -> dict:
    return {f: (get_secret_value(row, f) or "") for f in secret_fields}


def apply_secret_updates(row, spec: ProviderSpec, provided: dict) -> None:
    """Update only provided secret fields. Empty string clears a field."""
    enc = dict(row.encrypted_secrets or {})
    for field in spec.secret_fields():
        if field not in provided:
            continue
        value = (provided.get(field) or "").strip()
        if value == "":
            enc.pop(field, None)
        else:
            enc[field] = encrypt_secret(value)
    row.encrypted_secrets = enc


def apply_public_updates(row, spec: ProviderSpec, provided: dict) -> None:
    pub = dict(row.public_config or {})
    for field in spec.public_fields():
        if field not in provided:
            continue
        value = provided.get(field)
        if value is None or value == "":
            pub.pop(field, None)
        else:
            pub[field] = value
    row.public_config = pub


def has_required(row, spec: ProviderSpec) -> bool:
    pub = row.public_config or {}
    enc = row.encrypted_secrets or {}
    secret_keys = set(spec.secret_fields())
    for field in spec.required_fields():
        if field in secret_keys:
            if not enc.get(field):
                return False
        elif not pub.get(field):
            return False
    return True


def has_any_config(row) -> bool:
    return bool(row.public_config) or bool(row.encrypted_secrets)


def saved_status(row, spec: ProviderSpec) -> str:
    """Status after a save/enable (never 'online' — that requires a test)."""
    if not has_any_config(row):
        return "not_configured"
    if not row.enabled:
        return "disabled"
    return "configured" if has_required(row, spec) else "not_configured"


def secret_previews(row, spec: ProviderSpec) -> dict:
    out: dict[str, dict] = {}
    for field in spec.secret_fields():
        value = get_secret_value(row, field)
        out[field] = {"configured": bool(value), "preview": mask_secret(value or "")}
    return out


def field_specs(spec: ProviderSpec) -> list[dict]:
    return [
        {
            "key": f.key,
            "label": f.label,
            "secret": f.secret,
            "required": f.required,
            "placeholder": f.placeholder,
        }
        for f in spec.fields
    ]


STATUS_DETAIL = {
    "online": "Online",
    "configured": "Configured",
    "not_configured": "Not configured",
    "error": "Error",
    "disabled": "Disabled",
}
