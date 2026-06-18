"""Deterministic intent router for AI chat (3.9).

Classifies a user message into one of (priority order):
    finance_transaction > task_command > note_creation > memory_candidate > general_chat

For finance, it parses the Indonesian money amount and infers INCOME vs EXPENSE so the
chat layer can deterministically create a finance proposal instead of leaving routing to
the LLM (which sometimes answered "completed" or mis-stored the amount as a memory).

Finance routing requires a QUALIFIED money amount — a currency marker (Rp) or a magnitude
unit (ribu/rb/juta/jt/miliar/k) — OR a bare large number together with an income/expense
verb. Bare numbers alone (years, phone numbers, OTPs, quantities like "3 buku") do NOT
trigger finance.

Pure functions, no I/O — safe to call before the provider plan is resolved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

FINANCE = "finance_transaction"
TASK = "task_command"
NOTE = "note_creation"
MEMORY = "memory_candidate"
GENERAL = "general_chat"

# --- keyword sets (word-boundary matched so "bayaran" != "bayar") ----------- #
_INCOME_RE = re.compile(
    r"\b(pendapatan|pemasukan|pemasukkan|income|gaji(?:an)?|bayaran|honor|fee|"
    r"dapat\s+(?:uang|duit|project|proyek|bayaran|gaji|job|client|klien)|"
    r"terima\s+(?:uang|duit|pembayaran|transfer)|untung|profit|bonus|thr|komisi|"
    r"dibayar|cuan)\b",
    re.IGNORECASE,
)
_EXPENSE_RE = re.compile(
    r"\b(pengeluaran|expense|spending|belanja|jajan|bayar|beli|membeli|"
    r"keluar\s+(?:uang|duit)|biaya|ongkos|tagihan|top\s*up|bayarin)\b",
    re.IGNORECASE,
)

# A QUALIFIED money token: currency-marked, OR a magnitude unit, OR an attached "k".
# Single bare letters m/b are intentionally NOT units (they collide with Indonesian
# words like "mangga"/"buku"). Units are anchored with (?![a-z]) so they cannot consume
# the first letter of the next word.
_UNIT = r"(?:ribu|rb|juta|jt|miliar|milyar)"
_QUALIFIED_MONEY_RE = re.compile(
    r"rp\.?\s*\d[\d.,]*\s*" + _UNIT + r"(?![a-z])"   # Rp 1,5 juta
    r"|rp\.?\s*\d[\d.,]*"                            # Rp 100.000
    r"|\d[\d.,]*\s*" + _UNIT + r"(?![a-z])"          # 500 ribu / 50rb
    r"|\d[\d.,]*k(?![a-z\d])",                       # 50k (attached k)
    re.IGNORECASE,
)

# Explicit "remember" requests → memory (never finance).
_EXPLICIT_REMEMBER_RE = re.compile(
    r"\b(ingat|inget|simpan|catat)\s+(?:bahwa|kalau|kalo|sebagai\s+memory|ini)\b"
    r"|\bremember\s+that\b|\bsave\s+(?:this\s+)?(?:as\s+memory|that)\b|\bnote\s+that\b"
    r"|\bpreferensi\s+saya\b|\bmulai\s+sekarang\b",
    re.IGNORECASE,
)

# Task / note commands (lower priority than finance).
_TASK_RE = re.compile(
    r"\b(buat(?:kan)?|tambah(?:kan)?|create|add|ingatkan|reminder|remind)\s+"
    r"(?:task|tugas|todo|to-?do|pekerjaan|agenda)\b"
    r"|\btambah(?:kan)?\s+(?:ke\s+)?(?:task|tugas|todo)\b",
    re.IGNORECASE,
)
_NOTE_RE = re.compile(
    r"\b(buat(?:kan)?|tambah(?:kan)?|create|add|tulis(?:kan)?|simpan)\s+"
    r"(?:note|catatan|memo)\b",
    re.IGNORECASE,
)

_UNIT_MULT = {
    "ribu": 1_000, "rb": 1_000, "k": 1_000,
    "juta": 1_000_000, "jt": 1_000_000,
    "miliar": 1_000_000_000, "milyar": 1_000_000_000,
}
# Number + optional unit, used to extract the value of one already-qualified token.
_NUM_UNIT_RE = re.compile(r"(\d[\d.,]*)\s*(ribu|rb|juta|jt|miliar|milyar|k)?", re.IGNORECASE)


def _to_number(num_raw: str, has_multiplier: bool) -> Optional[float]:
    """Resolve a numeric string, disambiguating thousands-grouping from a decimal.

    "2.500"/"1,000,000" → grouping (2500 / 1000000). "1.5"/"1,5" with a multiplier
    → decimal (1.5). "100.000" (currency, no multiplier) → grouping (100000).
    """
    s = num_raw.strip()
    if not s:
        return None
    # Pure thousands grouping: 1-3 digits then repeated groups of exactly 3.
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return float(re.sub(r"[.,]", "", s))
    try:
        if has_multiplier:
            # Small quantity with a decimal separator (1.5 / 1,5).
            return float(s.replace(",", "."))
        # Plain integer; strip any stray separators.
        return float(re.sub(r"[.,]", "", s))
    except ValueError:
        return None


def parse_idr_amount(raw) -> Optional[int]:
    """Parse an Indonesian money phrase/value into an integer rupiah amount.

    "500 ribu"->500000, "50rb"->50000, "1 juta"->1000000, "1.5 juta"/"1,5 juta"->1500000,
    "Rp 100.000"->100000, "2.500 ribu"->2500000, "100000"->100000. Returns None when no
    number is present. Lenient (accepts bare numbers) — used to normalize an amount FIELD.
    """
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(round(float(raw)))
    s = re.sub(r"(rp\.?|idr)", " ", str(raw).strip().lower())
    if not s:
        return None
    m = _NUM_UNIT_RE.search(s)
    if not m or not m.group(1):
        return None
    suffix = (m.group(2) or "").lower()
    mult = _UNIT_MULT.get(suffix, 1)
    value = _to_number(m.group(1), mult > 1)
    if value is None:
        return None
    result = int(round(value * mult))
    return result if result > 0 else None


def _qualified_amounts(text: str) -> List[int]:
    """All distinct QUALIFIED money amounts (currency/unit-marked) in the message."""
    out: List[int] = []
    for m in _QUALIFIED_MONEY_RE.finditer(text):
        val = parse_idr_amount(m.group(0))
        if val is not None:
            out.append(val)
    return out


def _bare_money_with_verb(text: str, has_verb: bool) -> Optional[int]:
    """A bare number counts as money ONLY with an income/expense verb, when it's >=1000
    and not a plausible 4-digit year (so phone numbers/OTPs/years don't become amounts)."""
    if not has_verb:
        return None
    for m in re.finditer(r"\b(\d{3,})\b", text):
        digits = m.group(1)
        n = int(digits)
        if n >= 1000 and not (len(digits) == 4 and 1900 <= n <= 2099):
            return n
    return None


def _detect_type(text: str) -> Optional[str]:
    """INCOME / EXPENSE / None from keyword presence (earliest keyword wins ties)."""
    im = _INCOME_RE.search(text)
    em = _EXPENSE_RE.search(text)
    if im and not em:
        return "INCOME"
    if em and not im:
        return "EXPENSE"
    if im and em:
        return "INCOME" if im.start() <= em.start() else "EXPENSE"
    return None


_DESC_STOP = re.compile(
    r"\b(saya|aku|gue|gw|dapat|dapet|barusan|tadi|hari\s+ini|untuk|buat|dari|sebesar|"
    r"senilai|sejumlah|rp|idr|ribu|rb|juta|jt|miliar|milyar|uang|duit|yang|sudah|udah)\b",
    re.IGNORECASE,
)


def _extract_description(text: str, txn_type: Optional[str]) -> str:
    """Best-effort meaningful label, e.g. 'Project', 'Makan', else type-based default."""
    after = re.search(
        r"\b(?:pendapatan|pemasukan|pengeluaran|expense|belanja|jajan|bayar|beli|"
        r"dapat|gaji|untuk|buat)\s+([a-zA-Z][a-zA-Z\s]{1,40}?)(?=\s*(?:rp|\d|sebesar|senilai|$))",
        text,
        re.IGNORECASE,
    )
    if after:
        phrase = re.sub(r"\s+", " ", _DESC_STOP.sub(" ", after.group(1))).strip(" .,-")
        if len(phrase) >= 2:
            return phrase[:60].title()
    if "project" in text.lower() or "proyek" in text.lower():
        return "Project"
    if txn_type == "INCOME":
        return "Pemasukan"
    if txn_type == "EXPENSE":
        return "Pengeluaran"
    return "Transaksi"


@dataclass
class IntentResult:
    intent: str
    txn_type: Optional[str] = None      # "INCOME" | "EXPENSE" | None (unclear)
    amount: Optional[int] = None        # rupiah integer | None (unclear)
    currency: str = "IDR"
    description: str = ""
    needs_clarification: bool = False   # finance but amount/type/count unclear

    @property
    def is_finance(self) -> bool:
        return self.intent == FINANCE


def classify(message: str) -> IntentResult:
    """Classify a single user message. Finance has top priority on a qualified money signal."""
    text = (message or "").strip()
    if not text:
        return IntentResult(GENERAL)

    explicit_remember = bool(_EXPLICIT_REMEMBER_RE.search(text))
    has_income = bool(_INCOME_RE.search(text))
    has_expense = bool(_EXPENSE_RE.search(text))

    amounts = _qualified_amounts(text)
    bare = _bare_money_with_verb(text, has_income or has_expense) if not amounts else None
    amount = amounts[0] if amounts else bare

    # Finance only on a real money amount, and never when the user explicitly said "remember".
    if amount is not None and not explicit_remember:
        txn_type = _detect_type(text)
        if txn_type is None:
            txn_type = "INCOME" if has_income else ("EXPENSE" if has_expense else None)
        multiple = len(set(amounts)) > 1
        return IntentResult(
            FINANCE,
            txn_type=txn_type,
            amount=amount,
            currency="IDR",
            description=_extract_description(text, txn_type),
            needs_clarification=(txn_type is None or multiple),
        )

    if _TASK_RE.search(text):
        return IntentResult(TASK)
    if _NOTE_RE.search(text):
        return IntentResult(NOTE)
    if explicit_remember:
        return IntentResult(MEMORY)
    return IntentResult(GENERAL)


def is_money_message(message: str) -> bool:
    """Cheap predicate used by the memory gate: True if the message is a finance txn."""
    return classify(message).is_finance


def format_rupiah(amount: Optional[int]) -> str:
    if amount is None:
        return "Rp-"
    return "Rp" + f"{int(amount):,}".replace(",", ".")
