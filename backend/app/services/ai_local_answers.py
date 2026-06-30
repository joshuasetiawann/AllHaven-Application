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
_EN_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_EN_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_ZH_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
_ZH_MONTHS = ("1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月")

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
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "time": now.strftime("%H:%M:%S"),
        "timezone": getattr(settings, "APP_TIMEZONE", "") or str(now.tzinfo),
        "utc_offset": now.strftime("%z"),
        "weekday": _ID_WEEKDAYS[now.weekday()],
        "weekday_en": _EN_WEEKDAYS[now.weekday()],
        "weekday_zh": _ZH_WEEKDAYS[now.weekday()],
        "date_label": f"{now.day} {_ID_MONTHS[now.month - 1]} {now.year}",
        "date_label_en": f"{_EN_MONTHS[now.month - 1]} {now.day}, {now.year}",
        "date_label_zh": f"{now.year}年{_ZH_MONTHS[now.month - 1]}{now.day}日",
    }


def _preferred_language(message: str, response_language: str | None) -> str:
    if response_language in {"id", "en", "zh-Hant"}:
        return response_language
    lower = (message or "").lower()
    if any(token in lower for token in ("what time", "current time", "time now", "today", "current date")):
        return "en"
    return "id"


def direct_answer(message: str, response_language: str | None = None) -> dict | None:
    """Return a direct local answer if the message is a known tiny query."""
    text = " ".join((message or "").lower().split())
    if not text:
        return None

    wants_time = bool(_TIME_RE.search(text))
    wants_date = bool(_DATE_RE.search(text))
    if not wants_time and not wants_date:
        return None

    p = time_payload()
    lang = _preferred_language(message, response_language)
    weekday = p["weekday_zh"] if lang == "zh-Hant" else p["weekday_en"] if lang == "en" else p["weekday"]
    date_label = p["date_label_zh"] if lang == "zh-Hant" else p["date_label_en"] if lang == "en" else p["date_label"]
    if wants_time and wants_date:
        if lang == "en":
            content = f"It is {p['time']} ({p['timezone']}), {weekday}, {date_label}."
        elif lang == "zh-Hant":
            content = f"現在是 {p['time']}（{p['timezone']}），{weekday}，{date_label}。"
        else:
            content = f"Sekarang pukul {p['time']} ({p['timezone']}), {weekday}, {date_label}."
    elif wants_time:
        if lang == "en":
            content = f"It is {p['time']} ({p['timezone']})."
        elif lang == "zh-Hant":
            content = f"現在是 {p['time']}（{p['timezone']}）。"
        else:
            content = f"Sekarang pukul {p['time']} ({p['timezone']})."
    else:
        if lang == "en":
            content = f"Today is {weekday}, {date_label}."
        elif lang == "zh-Hant":
            content = f"今天是 {weekday}，{date_label}。"
        else:
            content = f"Hari ini {weekday}, {date_label}."
    return {"content": content, "payload": p, "tool": "get_current_time"}
