"""Deterministic natural-language schedule/routine parser.

Turns a request like "buatin jadwal 3 hari, pagi gym, siang makan, malam ngoding"
into structured, non-overlapping, timed daily blocks GROUPED BY THE PERIOD THE USER
NAMED (pagi/siang/malam) — so "gym malem" lands in the evening, not gym's usual
afternoon slot — under ONE reviewable multi-day approval, instead of the LLM
free-emitting a single giant all-day event.

Pure functions, no I/O — mirrors ``ai_intent_router``. Returns ``None`` when the
message is not a recognizable schedule request so the caller falls back to the LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Action verb (incl. colloquial buatin/bikinin) + a schedule noun; OR "jadwalkan".
_TRIGGER_RE = re.compile(
    r"\b(buat\w*|bikin\w*|atur\w*|susun\w*|rancang\w*|set)\b[^.!?]*\b(jadwal\w*|rutinitas|routine|schedule|agenda)\b"
    r"|\bjadwal(kan|in)\b",
    re.IGNORECASE,
)

_DAYS_RE = re.compile(r"(\d{1,2})\s*hari", re.IGNORECASE)
_WEEK_RE = re.compile(r"\b(seminggu|satu minggu|1 minggu|sepekan)\b", re.IGNORECASE)

# Period markers the user can say; the one they name wins over an activity default.
_PERIOD_MARKERS = [
    ("morning", re.compile(r"\b(pagi|subuh)\b", re.IGNORECASE)),
    ("afternoon", re.compile(r"\b(siang|sore)\b", re.IGNORECASE)),
    ("evening", re.compile(r"\b(malam|malem|petang)\b", re.IGNORECASE)),
]
_PERIOD_BASE = {"morning": (6, 0), "afternoon": (12, 0), "evening": (19, 0)}
_PERIOD_ORDER = ["morning", "afternoon", "evening"]

_MAX_BLOCK_MIN = 240
_MAX_DAYS = 14
_MAX_EVENTS = 50
_DAY_END = 23 * 60 + 30   # never run into 23:59 / all-day


# Activity alias -> (title, default_hour, default_min, duration_min, default_period).
# default_* time is used only when the activity lands in its OWN default period;
# otherwise it stacks from the named period's base time. Longest aliases win so
# "kerja malam ngoding" -> one Ngoding block (not Kerja + Ngoding).
_ACTIVITY_DEFAULTS: dict[str, Tuple[str, int, int, int, str]] = {
    "kerja malam ngoding": ("Ngoding", 20, 0, 120, "evening"),
    "baca buku": ("Baca Buku", 7, 45, 45, "morning"),
    "makan siang": ("Makan Siang", 12, 0, 45, "afternoon"),
    "makan malam": ("Makan Malam", 19, 0, 45, "evening"),
    "makan pagi": ("Sarapan", 7, 0, 30, "morning"),
    "jogging": ("Jogging", 6, 0, 45, "morning"),
    "lari": ("Lari Pagi", 6, 0, 45, "morning"),
    "olahraga": ("Olahraga", 6, 0, 45, "morning"),
    "senam": ("Senam", 6, 0, 45, "morning"),
    "badminton": ("Badminton", 6, 0, 60, "morning"),
    "bulutangkis": ("Badminton", 6, 0, 60, "morning"),
    "renang": ("Renang", 6, 0, 60, "morning"),
    "sepeda": ("Sepedaan", 6, 0, 60, "morning"),
    "yoga": ("Yoga", 6, 0, 45, "morning"),
    "meditasi": ("Meditasi", 5, 30, 20, "morning"),
    "sarapan": ("Sarapan", 7, 0, 30, "morning"),
    "membaca": ("Baca Buku", 7, 45, 45, "morning"),
    "baca": ("Baca Buku", 7, 45, 45, "morning"),
    "futsal": ("Futsal", 16, 0, 90, "afternoon"),
    "basket": ("Basket", 16, 0, 90, "afternoon"),
    "gym": ("Gym", 13, 0, 90, "afternoon"),
    "fitness": ("Gym", 13, 0, 90, "afternoon"),
    "makan": ("Makan", 12, 0, 45, "afternoon"),
    "belajar": ("Belajar", 15, 0, 120, "afternoon"),
    "study": ("Belajar", 15, 0, 120, "afternoon"),
    "rapat": ("Rapat", 14, 0, 60, "afternoon"),
    "meeting": ("Meeting", 14, 0, 60, "afternoon"),
    "ngoding": ("Ngoding", 20, 0, 120, "evening"),
    "coding": ("Ngoding", 20, 0, 120, "evening"),
    "kerja": ("Kerja", 9, 0, 120, "afternoon"),
    "nonton": ("Nonton", 21, 0, 90, "evening"),
    "tidur": ("Tidur", 22, 0, 30, "evening"),
}
_ALIASES_BY_LEN = sorted(_ACTIVITY_DEFAULTS, key=len, reverse=True)


@dataclass
class ScheduleBlock:
    title: str
    start_time: str        # "HH:MM" 24h
    duration_min: int
    time_period: str


@dataclass
class ScheduleDraft:
    repeat_days: int
    blocks: List[ScheduleBlock]


def _extract_days(message: str) -> int:
    m = _DAYS_RE.search(message)
    if m:
        return max(1, min(_MAX_DAYS, int(m.group(1))))
    if _WEEK_RE.search(message):
        return 7
    return 7  # spec default when a routine is requested without an explicit count


def _detect_period(segment: str) -> Optional[str]:
    """The earliest-named period marker in a segment, or None."""
    best, best_pos = None, 1 << 30
    for period, rx in _PERIOD_MARKERS:
        m = rx.search(segment)
        if m and m.start() < best_pos:
            best, best_pos = period, m.start()
    return best


def _activities_in(segment: str) -> List[Tuple[str, int, int, int, str]]:
    """Non-overlapping activity aliases in a segment, in reading order. Longest
    aliases reserve their span so a sub-word (kerja/ngoding inside "kerja malam
    ngoding") is not double-counted."""
    text = segment.lower()
    spans: list[tuple[int, int]] = []
    hits: list[tuple[int, Tuple]] = []
    for alias in _ALIASES_BY_LEN:
        idx = text.find(alias)
        if idx == -1:
            continue
        end = idx + len(alias)
        if any(not (end <= s or idx >= e) for s, e in spans):
            continue
        spans.append((idx, end))
        hits.append((idx, _ACTIVITY_DEFAULTS[alias]))
    hits.sort(key=lambda h: h[0])
    return [act for _, act in hits]


def _assign_times(by_period: dict[str, list]) -> List[ScheduleBlock]:
    """Stack each period's activities in appearance order from the period base time,
    using an activity's default time only when it lands in its own period and hasn't
    been passed. Caps every block at 4h and keeps it out of the 23:59/all-day zone."""
    blocks: List[ScheduleBlock] = []
    for period in _PERIOD_ORDER:
        base_h, base_m = _PERIOD_BASE[period]
        cursor = base_h * 60 + base_m
        for title, dh, dm, dur, dperiod in by_period.get(period, []):
            default_start = dh * 60 + dm
            start = max(cursor, default_start) if dperiod == period else cursor
            dur = max(5, min(_MAX_BLOCK_MIN, dur))
            end = min(start + dur, _DAY_END)
            start = min(start, end - 5)
            blocks.append(ScheduleBlock(
                title=title,
                start_time=f"{start // 60:02d}:{start % 60:02d}",
                duration_min=end - start,
                time_period=period,
            ))
            cursor = end
    return blocks


def parse_schedule(message: str) -> Optional[ScheduleDraft]:
    """Parse a routine request into period-grouped timed daily blocks, or None."""
    if not message or not _TRIGGER_RE.search(message):
        return None

    days = _extract_days(message)
    by_period: dict[str, list] = {"morning": [], "afternoon": [], "evening": []}
    seen: set[tuple[str, str]] = set()
    current: Optional[str] = None
    for segment in re.split(r"[,\n;]|\bdan\b|\blalu\b|\bkemudian\b", message):
        marker = _detect_period(segment)
        if marker:
            current = marker
        for act in _activities_in(segment):
            period = current or act[4]   # the period the user named wins; else default
            key = (act[0], period)
            if key in seen:
                continue
            seen.add(key)
            by_period[period].append(act)

    blocks = _assign_times(by_period)
    if not blocks:
        return None  # a schedule verb but no recognizable activity -> let the LLM try
    if days * len(blocks) > _MAX_EVENTS:
        days = max(1, _MAX_EVENTS // len(blocks))
    return ScheduleDraft(repeat_days=days, blocks=blocks)
