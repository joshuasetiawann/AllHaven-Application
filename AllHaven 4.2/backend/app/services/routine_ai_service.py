"""AI routine draft generation.

Generate-only: this module NEVER writes routines to the database. It asks the
workspace's configured AI provider for a short set of routine ideas, validates
and normalizes them server-side (slot-aware times, capped count), and returns
plain draft dicts for the user to review/edit before they explicitly save.

Honest by design: if no provider is configured the caller gets a clear
``not_configured`` status instead of fabricated output, and any failure surfaces
as an ``error`` status rather than a silent empty success.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.principal import Principal

MAX_DRAFTS = 8

# Inclusive-lower, exclusive-upper hour windows for each slot.
PERIOD_WINDOWS: dict[str, tuple[int, int]] = {
    "morning": (5, 12),
    "afternoon": (12, 17),
    "evening": (17, 24),
}
PERIOD_DEFAULT_TIME: dict[str, str] = {
    "morning": "07:00",
    "afternoon": "13:00",
    "evening": "19:00",
}
ALLOWED_REPEAT = {"once", "daily", "weekly", "monthly"}
ALLOWED_DAYS = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}


def generate_drafts(
    db: Session,
    principal: Principal,
    *,
    prompt: str,
    date: str,
    period: str,
    use_context: bool = True,
) -> dict:
    """Return ``{status, message, drafts}``. Never raises, never writes.

    ``status`` is one of: ``ok`` | ``not_configured`` | ``blocked`` | ``error``.
    Drafts are validated dicts ready for the review modal; they are NOT saved.
    """
    if period not in PERIOD_WINDOWS:
        period = "morning"

    context = _build_context(db, principal, date, use_context)
    message = _build_prompt(prompt, date, period, context)

    from app.services import ai_provider_router

    result = ai_provider_router.run_chat(
        db, principal, messages=[{"role": "user", "content": message}]
    )

    if not result.get("ok"):
        error = result.get("error") or "error"
        if error in ("not_configured", "unknown_provider"):
            return {
                "status": "not_configured",
                "message": "Configure AI provider first.",
                "drafts": [],
            }
        if error in ("disabled", "blocked", "external_disabled"):
            # Provider exists but is turned off (or external use is blocked). Keep
            # run_chat's specific message — e.g. "configured but disabled. Enable
            # it in Settings." — instead of telling the user to configure it again.
            return {
                "status": "blocked",
                "message": result.get("content")
                or "This AI provider is turned off. Enable it in Settings → AI Providers.",
                "drafts": [],
            }
        return {
            "status": "error",
            "message": result.get("content") or "AI generation failed. Please try again.",
            "drafts": [],
        }

    drafts = _parse_drafts(result.get("content") or "", date, period)
    if not drafts:
        return {
            "status": "error",
            "message": "The AI did not return any usable routines. Try a more specific prompt.",
            "drafts": [],
        }
    return {"status": "ok", "message": "", "drafts": drafts}


def _build_context(db: Session, principal: Principal, date: str, use_context: bool) -> str:
    """Best-effort real context (open tasks + same-day routines). Never raises."""
    if not use_context:
        return ""
    lines: list[str] = []
    try:
        from app.services import task_service

        tasks = task_service.list_tasks(db, principal, limit=20)
        open_titles = [t.title for t in tasks if (t.status or "").upper() not in ("DONE", "ARCHIVED")]
        if open_titles:
            lines.append("Open tasks: " + "; ".join(open_titles[:8]))
    except Exception:
        pass
    try:
        from app.services import calendar_service

        day_start = datetime.fromisoformat(f"{date}T00:00:00")
        day_end = datetime.fromisoformat(f"{date}T23:59:59")
        existing = calendar_service.list_events(db, principal, start=day_start, end=day_end)
        if existing:
            lines.append(
                "Existing routines on this date: "
                + "; ".join(f"{e.title} at {e.start_at.strftime('%H:%M')}" for e in existing[:10])
            )
    except Exception:
        pass
    return "\n".join(lines)


def _build_prompt(prompt: str, date: str, period: str, context: str) -> str:
    lo, hi = PERIOD_WINDOWS[period]
    request = (prompt or "").strip() or f"Plan a balanced, realistic {period} routine."
    parts = [
        "You are a calm, practical daily-routine planner for the AllHaven app.",
        f"Plan routine items for {date} during the {period} window "
        f"(between {lo:02d}:00 and {hi:02d}:00, 24-hour time).",
        f"User request: {request}",
    ]
    if context:
        parts.append("Helpful context (do not invent beyond it):\n" + context)
    parts.append(
        "Return ONLY a JSON array (no prose, no markdown) with at most 8 objects. "
        "Each object has keys: "
        'title (string, required, <= 80 chars); '
        'time ("HH:MM" 24-hour, inside the window); '
        "duration_minutes (integer 5-240, optional); "
        "description (string, optional); "
        "location (string, optional); "
        "repeat_rule (one of: once, daily, weekly, monthly); "
        "repeat_days (array from mon,tue,wed,thu,fri,sat,sun, optional); "
        "all_day (boolean, optional). "
        "Keep it concise and realistic. Return [] if you cannot help."
    )
    return "\n\n".join(parts)


def _parse_drafts(content: str, date: str, period: str) -> list[dict]:
    raw = _load_json_array(content)
    if not isinstance(raw, list):
        return []
    drafts: list[dict] = []
    for item in raw[:MAX_DRAFTS]:
        draft = _normalize_draft(item, date, period)
        if draft:
            drafts.append(draft)
    return drafts


def _load_json_array(content: str) -> object:
    text = (content or "").strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` fence if the model wrapped its output.
        segments = text.split("```")
        if len(segments) >= 2:
            text = segments[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # Fall back to the first bracketed array in the text.
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
        return None


def _parse_hhmm(value: str) -> tuple[Optional[int], Optional[int]]:
    parts = str(value or "").strip().split(":")
    if len(parts) != 2:
        return None, None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None, None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None, None


def _normalize_draft(item: object, date: str, period: str) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()[:80]
    if not title:
        return None

    all_day = bool(item.get("all_day", False))
    lo, hi = PERIOD_WINDOWS[period]
    hour, minute = _parse_hhmm(str(item.get("time") or ""))
    # Enforce the slot window: snap anything missing/out-of-range to the default.
    if hour is None or not (lo <= hour < hi):
        dh, dm = PERIOD_DEFAULT_TIME[period].split(":")
        hour, minute = int(dh), int(dm)

    try:
        start_dt = datetime.fromisoformat(f"{date}T{hour:02d}:{minute:02d}:00")
    except ValueError:
        return None

    end_iso: Optional[str] = None
    if not all_day:
        try:
            duration = int(item.get("duration_minutes"))
        except (TypeError, ValueError):
            duration = 0
        if 5 <= duration <= 240:
            end_iso = (start_dt + timedelta(minutes=duration)).isoformat()

    repeat_rule = str(item.get("repeat_rule") or "once").strip().lower()
    if repeat_rule not in ALLOWED_REPEAT:
        repeat_rule = "once"

    repeat_days: list[str] = []
    raw_days = item.get("repeat_days")
    if isinstance(raw_days, list):
        for day in raw_days:
            key = str(day).strip().lower()[:3]
            if key in ALLOWED_DAYS and key not in repeat_days:
                repeat_days.append(key)

    description = str(item.get("description") or "").strip()[:1000] or None
    location = str(item.get("location") or "").strip()[:255] or None

    return {
        "title": title,
        "description": description,
        "location": location,
        "start_at": start_dt.isoformat(),
        "end_at": end_iso,
        "all_day": all_day,
        "time_period": period,
        "repeat_rule": repeat_rule,
        "repeat_days": repeat_days,
    }
