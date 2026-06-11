"""Shared helper for turning an agent outcome into a human-readable chat message body.

The single most visible AI bug was the literal word "completed" (or a blank bubble)
showing up as the assistant's reply. That happened because three call sites persisted
``content if status == "completed" and content else (error or status)`` — so an empty
``content`` fell through to the raw status sentinel (``"completed"``/``"running"``/…),
which the frontend then rendered verbatim as if it were the AI's prose.

``display_text`` is the one place that decides what text a user actually sees. It NEVER
returns a bare status word: real prose wins; otherwise an explicit error; otherwise a
warm, human sentence keyed by status. Pure function, no I/O.
"""
from __future__ import annotations

from typing import Optional

# Status values that are pipeline bookkeeping, NOT something a human should ever read
# as the assistant's answer.
_SENTINELS = {"completed", "complete", "running", "queued", "pending", "ok", "done", ""}

# Warm, human fallbacks (Bahasa Indonesia — matches the user's language) for the case
# where an agent finished but produced no usable text, or could not run at all.
_BY_STATUS = {
    "not_configured": (
        "Belum ada AI provider yang aktif, jadi saya belum bisa menjawab. "
        "Aktifkan salah satu dulu di Settings → AI Providers ya."
    ),
    "disabled": (
        "Provider AI ini sedang dimatikan. Aktifkan lagi di Settings → AI Providers, "
        "lalu coba kirim ulang pesannya."
    ),
    "blocked": (
        "Provider eksternal ini sedang diblokir oleh kebijakan privasi kamu. "
        "Kamu bisa mengubahnya di Settings → Privacy & Safety."
    ),
    "unsupported": (
        "Maaf, model ini belum bisa memproses lampiran tersebut. "
        "Coba pilih model lain yang mendukung gambar."
    ),
    "error": (
        "Maaf, ada kendala saat memproses pesan ini. Coba kirim ulang sebentar lagi, "
        "atau pilih model AI lain di Settings → AI Providers."
    ),
}

# When an agent reports success but hands back nothing usable.
_EMPTY_SUCCESS = (
    "Maaf, saya belum sempat menyusun jawaban untuk pesan itu. "
    "Coba kirim ulang, atau pilih model AI lain di Settings → AI Providers ya."
)

_GENERIC = (
    "Maaf, saya belum bisa menjawab sekarang. Coba kirim ulang sebentar lagi ya."
)


def display_text(status: Optional[str], content: Optional[str], error: Optional[str] = None) -> str:
    """The assistant message body a human will read. Never a bare status sentinel.

    Priority: real prose → explicit error → warm status-keyed sentence → generic.
    """
    text = (content or "").strip()
    if text and text.lower() not in _SENTINELS:
        return content  # genuine prose (return the original, un-stripped form)

    err = (error or "").strip()
    if err and err.lower() not in _SENTINELS:
        return error

    st = (status or "").strip().lower()
    if st in ("completed", "complete", "ok", "done", "running", "queued"):
        # Finished (or claimed success) but no real text came back.
        return _EMPTY_SUCCESS
    if st in _BY_STATUS:
        return _BY_STATUS[st]
    return _GENERIC
