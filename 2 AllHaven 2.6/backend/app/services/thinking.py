"""Thinking Mode — reasoning depth + sampling, separate from Chat Mode.

Chat Mode (parallel / debate / reasoning) controls *collaboration style*.
Thinking Mode (fast / balance / thinking / deep) controls *reasoning depth* and
the model's sampling settings. Default is ``balance``.
"""

from __future__ import annotations

THINKING_MODES = ("fast", "balance", "thinking", "deep")
DEFAULT_THINKING = "balance"

# Sampling per thinking mode (lower temperature = more careful/grounded).
_PARAMS = {
    "fast": {"temperature": 0.35, "top_p": 0.85},
    "balance": {"temperature": 0.25, "top_p": 0.80},
    "thinking": {"temperature": 0.15, "top_p": 0.75},
    "deep": {"temperature": 0.10, "top_p": 0.70},
}

# Thinking Mode -> reasoning-council depth (which roles run). Used only by the
# Reasoning chat mode; Parallel/Debate just use the sampling params.
_DEPTH = {"fast": "fast", "balance": "balanced", "thinking": "deep", "deep": "deep"}


def normalize_thinking(mode: str | None) -> str:
    m = (mode or "").lower()
    return m if m in THINKING_MODES else DEFAULT_THINKING


def thinking_params(mode: str | None) -> dict:
    """Sampling params (temperature, top_p) for a thinking mode."""
    return dict(_PARAMS[normalize_thinking(mode)])


def reasoning_depth(mode: str | None) -> str:
    """Map a thinking mode to the reasoning-council depth (fast/balanced/deep)."""
    return _DEPTH[normalize_thinking(mode)]
