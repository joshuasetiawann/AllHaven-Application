"""Deterministic intent router for AI chat (3.9).

Classifies a user message into one of (priority order):
    finance_transaction > task_command > note_creation > memory_candidate > general_chat

For finance, it parses the Indonesian money amount and infers INCOME vs EXPENSE so the
chat layer can deterministically create a finance proposal instead of leaving routing to
the LLM (which sometimes answered "completed" or mis-stored the amount as a memory).

Pure functions, no I/O — safe to call before the provider plan is resolved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

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
# A money signal: an amount with a unit/currency, so "dapat 500 ribu" still routes finance.
_MONEY_AMOUNT_RE = re.compile(
    r"(?:rp\.?\s*)?\d[\d.,]*\s*(?:ribu|rb|juta|jt|miliar|milyar|m|k)\b"
    r"|rp\.?\s*\d[\d.,]*"
    r"|\b\d{4,}\b",
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

# Multiplier suffixes for Indonesian money.
_MULTIPLIERS = (
    (("miliar", "milyar", "billion", "b"), 1_000_000_000),
    (("juta", "jt", "million", "m"), 1_000_000),
    (("ribu", "rb", "k"), 1_000),
)
_AMOUNT_RE = re.compile(
    r"(\d[\d.,]*)\s*(miliar|milyar|juta|jt|ribu|rb|k|m|b)?", re.IGNORECASE
)


def parse_idr_amount(raw) -> Optional[int]:
    """Parse an Indonesian money phrase into an integer rupiah value.

    Handles: "500 ribu"->500000, "50rb"->50000, "1 juta"->1000000,
    "1.5 juta"/"1,5 juta"->1500000, "Rp 100.000"->100000, "100000"->100000.
    Returns None when no number is present.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(round(float(raw)))
    s = str(raw).strip().lower()
    if not s:
        return None
    s = re.sub(r"(rp\.?|idr)", " ", s)  # strip currency markers
    m = _AMOUNT_RE.search(s)
    if not m or not m.group(1):
        return None
    num_raw, suffix = m.group(1), (m.group(2) or "").lower()
    mult = 1
    for names, value in _MULTIPLIERS:
        if suffix in names:
            mult = value
            break
    try:
        if mult > 1:
            # With a multiplier the number is a small quantity ("1.5", "1,5") where
            # '.'/',' is the DECIMAL separator.
            n = num_raw.replace(" ", "").replace(",", ".")
            if n.count(".") > 1:  # e.g. stray grouping → keep only the last dot as decimal
                parts = n.split(".")
                n = "".join(parts[:-1]) + "." + parts[-1]
            value = float(n)
        else:
            # No multiplier: '.'/',' are THOUSANDS separators ("100.000" -> 100000).
            digits = re.sub(r"[.,\s]", "", num_raw)
            value = float(digits) if digits else 0.0
    except ValueError:
        return None
    result = int(round(value * mult))
    return result if result > 0 else None


def _detect_type(text: str) -> Optional[str]:
    """INCOME / EXPENSE / None from keyword presence (income wins ties for 'dapat ...')."""
    has_income = bool(_INCOME_RE.search(text))
    has_expense = bool(_EXPENSE_RE.search(text))
    if has_income and not has_expense:
        return "INCOME"
    if has_expense and not has_income:
        return "EXPENSE"
    if has_income and has_expense:
        # Pick whichever keyword appears first in the sentence.
        im = _INCOME_RE.search(text)
        em = _EXPENSE_RE.search(text)
        return "INCOME" if im.start() <= em.start() else "EXPENSE"
    return None


_DESC_STOP = re.compile(
    r"\b(saya|aku|gue|gw|dapat|dapet|barusan|tadi|hari\s+ini|untuk|buat|dari|sebesar|"
    r"senilai|sejumlah|rp|idr|ribu|rb|juta|jt|miliar|milyar|uang|duit|yang|sudah|udah)\b",
    re.IGNORECASE,
)


def _extract_description(text: str, txn_type: Optional[str]) -> str:
    """Best-effort meaningful label, e.g. 'Project', 'Makan', else type-based default."""
    # Word right after an income/expense keyword, before the amount.
    after = re.search(
        r"\b(?:pendapatan|pemasukan|pengeluaran|expense|belanja|jajan|bayar|beli|"
        r"dapat|gaji|untuk|buat)\s+([a-zA-Z][a-zA-Z\s]{1,40}?)(?=\s*(?:rp|\d|sebesar|senilai|$))",
        text,
        re.IGNORECASE,
    )
    if after:
        phrase = _DESC_STOP.sub(" ", after.group(1)).strip()
        phrase = re.sub(r"\s+", " ", phrase).strip(" .,-")
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
    # finance slots (only when intent == FINANCE)
    txn_type: Optional[str] = None      # "INCOME" | "EXPENSE" | None (unclear)
    amount: Optional[int] = None        # rupiah integer | None (unclear)
    currency: str = "IDR"
    description: str = ""
    needs_clarification: bool = False   # finance but amount/type unclear

    @property
    def is_finance(self) -> bool:
        return self.intent == FINANCE


def classify(message: str) -> IntentResult:
    """Classify a single user message. Finance has top priority on money signals."""
    text = (message or "").strip()
    if not text:
        return IntentResult(GENERAL)

    # 1) Explicit remember beats everything except a clear money transaction.
    explicit_remember = bool(_EXPLICIT_REMEMBER_RE.search(text))

    # 2) Finance: an income/expense verb OR a money amount present.
    has_income = bool(_INCOME_RE.search(text))
    has_expense = bool(_EXPENSE_RE.search(text))
    has_money_amount = bool(_MONEY_AMOUNT_RE.search(text))
    txn_type = _detect_type(text)
    amount = parse_idr_amount(text)

    money_intent = (has_income or has_expense or (has_money_amount and amount)) and amount is not None
    # A bare amount with no verb and no remember intent still counts as finance only
    # when there is a real money amount (avoid hijacking "umur saya 25").
    if money_intent and not explicit_remember:
        # Infer a type if keywords were absent: a "receive" verb → INCOME else EXPENSE.
        if txn_type is None:
            if has_income:
                txn_type = "INCOME"
            elif has_expense:
                txn_type = "EXPENSE"
        return IntentResult(
            FINANCE,
            txn_type=txn_type,
            amount=amount,
            currency="IDR",
            description=_extract_description(text, txn_type),
            needs_clarification=(txn_type is None or amount is None),
        )

    # 3) Task / note commands.
    if _TASK_RE.search(text):
        return IntentResult(TASK)
    if _NOTE_RE.search(text):
        return IntentResult(NOTE)

    # 4) Explicit memory request.
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
