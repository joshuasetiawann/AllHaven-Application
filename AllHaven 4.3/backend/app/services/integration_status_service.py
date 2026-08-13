"""Placeholder detection shared by the integration/provider config services.

A value that merely *looks* real is reported ``configured`` — never ``online``,
which only a successful Test Connection can earn.
"""

from __future__ import annotations

from typing import Optional

# Values that indicate a placeholder rather than a real configuration.
_PLACEHOLDER_HINTS = (
    "changeme", "change-me", "placeholder", "example", "your-", "your_",
    "xxx", "todo", "<", "...",
)
_PLACEHOLDER_EXACT = {
    "", "none", "null", "disabled", "test", "sk-test", "your-api-key",
    "your_api_key", "api-key", "api_key", "apikey", "key", "secret",
}


def is_configured_value(value: Optional[str]) -> bool:
    """Return True only if a value looks like a real (non-placeholder) setting.

    This only filters *obvious* placeholders so they stay ``not_configured``. It is
    NOT a substitute for verification — a non-placeholder value is treated as
    ``configured``, never ``online`` (that requires a successful Test Connection).
    """
    if not value:
        return False
    normalized = value.strip().lower()
    if normalized in _PLACEHOLDER_EXACT:
        return False
    return not any(hint in normalized for hint in _PLACEHOLDER_HINTS)
