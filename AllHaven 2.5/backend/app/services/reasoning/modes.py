"""Reasoning modes and model (generation) settings.

A reasoning mode controls two things:
    * how deep the pipeline runs (which agent roles participate), and
    * the sampling settings (lower temperature for analytical work, higher only
      for creative tasks) — per the project's model_settings policy.
"""

from __future__ import annotations

from typing import List

REASONING_MODES = ("fast", "balanced", "deep")
DEFAULT_MODE = "balanced"

# Task types the intent detector can produce.
TASK_TYPES = (
    "analysis", "coding", "debugging", "business", "finance",
    "planning", "creative", "casual",
)

# Base generation settings (model_settings policy).
_DEFAULT = {"temperature": 0.2, "top_p": 0.8, "presence_penalty": 0, "frequency_penalty": 0}
_REASONING = {"temperature": 0.1, "top_p": 0.7, "presence_penalty": 0, "frequency_penalty": 0}
_CREATIVE = {"temperature": 0.7, "top_p": 0.9, "presence_penalty": 0, "frequency_penalty": 0}

# Tasks that should use low temperature for grounded, deterministic reasoning.
_ANALYTICAL = {"analysis", "coding", "debugging", "business", "finance", "planning"}


def normalize_mode(mode: str | None) -> str:
    return mode if mode in REASONING_MODES else DEFAULT_MODE


def params_for(task_type: str, mode: str) -> dict:
    """Generation params for a task + reasoning mode.

    Creative tasks get higher temperature (unless the user forces Deep, which
    always prefers precision). Analytical tasks and Deep mode get low temperature.
    """
    mode = normalize_mode(mode)
    if task_type == "creative" and mode != "deep":
        return dict(_CREATIVE)
    if mode == "deep":
        return dict(_REASONING)
    if mode == "fast":
        return dict(_DEFAULT)
    # balanced
    return dict(_REASONING) if task_type in _ANALYTICAL else dict(_DEFAULT)


def roles_for(mode: str) -> List[str]:
    """Which agent roles run, in order, for a reasoning mode."""
    return {
        "fast": ["analyst"],
        "balanced": ["analyst", "synthesizer"],
        "deep": ["analyst", "critic", "synthesizer"],
    }[normalize_mode(mode)]
