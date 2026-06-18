"""Deterministic local answers that should not need an AI provider.

Used for tiny factual workspace questions such as the current local time. This
keeps answers fast, avoids needless external calls, and works even when AI
providers are not configured.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings

_ID_WEEKDAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
_ID_MONTHS = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)

_TIME_RE = re.compile(
    r"(jam\s*(berapa|brp|berapoa)|pukul\s*berapa|sekarang\s+jam|"
    r"what\s+time|current\s+time|time\s+now)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"(tanggal\s*(berapa|brp)|hari\s+apa|sekarang\s+tanggal|"
    r"what\s+(date|day)|today'?s\s+date|current\s+date)",
    re.IGNORECASE,
)


def app_now() -> datetime:
    """Current datetime in the configured app timezone."""
    tz_name = (getattr(settings, "APP_TIMEZONE", "") or "Asia/Jakarta").strip()
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = datetime.now().astimezone().tzinfo
    return datetime.now(tz)


def time_payload() -> dict:
    now = app_now()
    return {
        "iso": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "timezone": getattr(settings, "APP_TIMEZONE", "") or str(now.tzinfo),
        "utc_offset": now.strftime("%z"),
        "weekday": _ID_WEEKDAYS[now.weekday()],
        "date_label": f"{now.day} {_ID_MONTHS[now.month - 1]} {now.year}",
    }


def direct_answer(message: str) -> dict | None:
    """Return a direct local answer if the message is a known tiny query."""
    text = " ".join((message or "").lower().split())
    if not text:
        return None

    wants_time = bool(_TIME_RE.search(text))
    wants_date = bool(_DATE_RE.search(text))
    if not wants_time and not wants_date:
        return None

    p = time_payload()
    if wants_time and wants_date:
        content = (
            f"Sekarang pukul {p['time']} ({p['timezone']}), "
            f"{p['weekday']}, {p['date_label']}."
        )
    elif wants_time:
        content = f"Sekarang pukul {p['time']} ({p['timezone']})."
    else:
        content = f"Hari ini {p['weekday']}, {p['date_label']}."
    return {"content": content, "payload": p, "tool": "get_current_time"}
