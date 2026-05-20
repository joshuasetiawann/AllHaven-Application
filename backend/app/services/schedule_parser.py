"""Deterministic natural-language schedule/routine parser.

Turns a request like "atur jadwal 7 hari ke depan, pagi jogging, sarapan, baca
buku, siang gym, belajar, malam ngoding" into structured, non-overlapping timed
daily blocks, so a routine request becomes ONE reviewable multi-day approval
instead of the LLM free-emitting a single giant all-day event (the reported bug).

Pure functions, no I/O — mirrors ``ai_intent_router``. If nothing recognizable is
found it returns ``None`` so the caller falls back to the normal LLM tool loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# An explicit "atur/buat/susun/jadwalkan ... jadwal/rutinitas/schedule/agenda".
# Requires an action verb + a schedule noun so "kapan jadwal meeting?" does NOT match.
_TRIGGER_RE = re.compile(
    r"\b(atur|buat|buatkan|susun|bikin|rancang|set)\b[^.!?]*\b(jadwal|jadwalku|rutinitas|routine|schedule|agenda)\b"
    r"|\b(jadwalkan|jadwalin)\b",
    re.IGNORECASE,
)

_DAYS_RE = re.compile(r"(\d{1,2})\s*hari", re.IGNORECASE)
_WEEK_RE = re.compile(r"\b(seminggu|satu minggu|1 minggu|sepekan)\b", re.IGNORECASE)

_MAX_BLOCK_MIN = 240   # spec: a single block is at most 4h
_MAX_DAYS = 14
_MAX_EVENTS = 50       # calendar_service.create_events_batch hard cap


@dataclass(frozen=True)
class _Act:
    title: str
    hour: int
    minute: int
    duration_min: int
    period: str


# Activity alias -> default (title, start, duration, period). Longest aliases win
# so "kerja malam ngoding" resolves to one Ngoding block (not Kerja + Ngoding).
_ACTIVITY_DEFAULTS: dict[str, _Act] = {
    "kerja malam ngoding": _Act("Ngoding", 20, 0, 120, "evening"),
    "baca buku": _Act("Baca Buku", 7, 45, 45, "morning"),
    "makan siang": _Act("Makan Siang", 12, 0, 45, "afternoon"),
    "makan malam": _Act("Makan Malam", 19, 0, 45, "evening"),
    "makan pagi": _Act("Sarapan", 7, 0, 30, "morning"),
    "jogging": _Act("Jogging", 6, 0, 45, "morning"),
    "lari": _Act("Lari Pagi", 6, 0, 45, "morning"),
    "olahraga": _Act("Olahraga", 6, 0, 45, "morning"),
    "sarapan": _Act("Sarapan", 7, 0, 30, "morning"),
    "membaca": _Act("Baca Buku", 7, 45, 45, "morning"),
    "meditasi": _Act("Meditasi", 5, 30, 20, "morning"),
    "gym": _Act("Gym", 13, 0, 90, "afternoon"),
    "fitness": _Act("Gym", 13, 0, 90, "afternoon"),
    "belajar": _Act("Belajar", 15, 0, 120, "afternoon"),
    "study": _Act("Belajar", 15, 0, 120, "afternoon"),
    "ngoding": _Act("Ngoding", 20, 0, 120, "evening"),
    "coding": _Act("Ngoding", 20, 0, 120, "evening"),
    "kerja": _Act("Kerja", 20, 0, 120, "evening"),
    "tidur": _Act("Tidur", 22, 0, 60, "evening"),
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


def _activities_in(segment: str) -> List[_Act]:
    """All non-overlapping activity aliases in a comma-segment, in reading order.

    Longest aliases are matched first and reserve their character span, so a
    sub-word alias inside a longer one (e.g. "kerja"/"ngoding" inside "kerja malam
    ngoding") is not double-counted.
    """
    text = segment.lower()
    spans: list[tuple[int, int]] = []
    hits: list[tuple[int, _Act]] = []
    for alias in _ALIASES_BY_LEN:
        start = text.find(alias)
        if start == -1:
            continue
        end = start + len(alias)
        if any(not (end <= s or start >= e) for s, e in spans):
            continue  # overlaps an already-claimed (longer) alias
        spans.append((start, end))
        hits.append((start, _ACTIVITY_DEFAULTS[alias]))
    hits.sort(key=lambda h: h[0])
    return [act for _, act in hits]


def _resolve_overlaps(blocks: List[ScheduleBlock]) -> List[ScheduleBlock]:
    """Push any block that starts before the previous one ends to start at that end,
    so the day's blocks never overlap. Stable order by start time."""
    def to_min(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    ordered = sorted(blocks, key=lambda b: to_min(b.start_time))
    prev_end = -1
    out: List[ScheduleBlock] = []
    for b in ordered:
        start = to_min(b.start_time)
        if start < prev_end:
            start = prev_end
        end = min(start + b.duration_min, 23 * 60 + 30)  # never run into 23:59/all-day
        start = min(start, end - 5)
        out.append(ScheduleBlock(
            title=b.title,
            start_time=f"{start // 60:02d}:{start % 60:02d}",
            duration_min=end - start,
            time_period=b.time_period,
        ))
        prev_end = end
    return out


def parse_schedule(message: str) -> Optional[ScheduleDraft]:
    """Parse a routine request into structured daily blocks, or None if it isn't one."""
    if not message or not _TRIGGER_RE.search(message):
        return None

    days = _extract_days(message)
    blocks: List[ScheduleBlock] = []
    seen: set[str] = set()
    # Split on commas / "dan" / newlines; each segment contributes its activities in order.
    for segment in re.split(r"[,\n]|\bdan\b", message):
        for act in _activities_in(segment):
            if act.title in seen:
                continue
            seen.add(act.title)
            blocks.append(ScheduleBlock(
                title=act.title,
                start_time=f"{act.hour:02d}:{act.minute:02d}",
                duration_min=min(act.duration_min, _MAX_BLOCK_MIN),
                time_period=act.period,
            ))

    if not blocks:
        return None  # a schedule verb but no recognizable activities -> let the LLM try
    blocks = _resolve_overlaps(blocks)
    # Keep the whole plan within the batch cap by trimming days, never splitting a day.
    if days * len(blocks) > _MAX_EVENTS:
        days = max(1, _MAX_EVENTS // len(blocks))
    return ScheduleDraft(repeat_days=days, blocks=blocks)
