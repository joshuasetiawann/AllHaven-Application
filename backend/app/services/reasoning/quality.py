"""Deterministic Reasoning Quality Layer.

These helpers do NOT depend on any model — they are pure functions that ground,
verify, and score an answer against the user's input. This is what actually
prevents the failure modes the project calls out: shallow/incorrect calculations,
invented Porter forces, reversed acquisition direction, irrelevant critique, and
ungrounded ("hallucinated") numbers. The model prompts steer toward these
standards; this layer catches and scores failures, and drives retry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.services.reasoning.modes import TASK_TYPES  # noqa: F401 (re-exported for convenience)

# --- intent / task detection ---------------------------------------------

_TASK_KEYWORDS: Dict[str, tuple] = {
    "finance": ("revenue", "ebitda", "margin", "profit", "valuation", "cash flow", "npv",
                "roi", "budget", "acquire", "acquisition", "investment", "pendapatan", "laba"),
    "business": ("strategy", "market", "porter", "competit", "swot", "go-to-market",
                 "business model", "pricing", "strategi", "pasar", "five forces"),
    "coding": ("code", "function", "python", "javascript", "typescript", "api",
               "refactor", "compile", "import ", "class ", "def "),
    "debugging": ("error", "traceback", "exception", "not working", "fails", "broken",
                  "debug", "crash", "stack trace"),
    "planning": ("plan", "roadmap", "schedule", "timeline", "milestone", "rencana", "jadwal"),
    "creative": ("story", "poem", "imagine", "brainstorm", "tagline", "slogan",
                 "puisi", "cerita", "write a song"),
}


def detect_task_type(text: str) -> str:
    """Classify the user's request into a task type (heuristic, deterministic)."""
    low = (text or "").lower()
    scores = {t: sum(1 for kw in kws if kw in low) for t, kws in _TASK_KEYWORDS.items()}
    best = max(scores, key=lambda t: scores[t]) if scores else "analysis"
    if scores.get(best, 0) == 0:
        return "casual" if len(low.split()) <= 4 else "analysis"
    return best


# --- numbers / facts / assumptions ---------------------------------------

_NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def extract_numbers(text: str) -> List[str]:
    return _NUM_RE.findall(text or "")


def _to_float(token: str) -> Optional[float]:
    try:
        return float(token.replace("$", "").replace(",", "").replace("%", "").strip())
    except (ValueError, AttributeError):
        return None


def _nums(text: str) -> List[float]:
    return [v for v in (_to_float(t) for t in extract_numbers(text)) if v is not None]


def extract_facts(text: str) -> dict:
    """Pull short declarative lines / lines with numbers as 'facts'."""
    facts: List[str] = []
    for chunk in re.split(r"[\n.;]", text or ""):
        s = chunk.strip()
        if s and (_NUM_RE.search(s) or len(s.split()) <= 14):
            facts.append(s)
    return {"facts": facts[:12], "numbers": extract_numbers(text)}


def extract_assumptions(text: str) -> List[str]:
    out: List[str] = []
    for chunk in re.split(r"[\n.]", text or ""):
        low = chunk.lower()
        if "assume" in low or "assumption" in low or "asums" in low:
            out.append(chunk.strip())
    return out


# --- numeric verification -------------------------------------------------


def project_revenue(base: float, growth_pct: float, years: int) -> List[float]:
    """Year-by-year projection. Index 0 is the base year (no growth applied yet)."""
    g = 1.0 + growth_pct / 100.0
    return [round(base * (g ** n), 2) for n in range(years + 1)]


def ebitda(revenue: float, margin_pct: float) -> float:
    return round(revenue * margin_pct / 100.0, 2)


def _close(a: float, b: float, *, rel: float = 0.01, abs_tol: float = 0.5) -> bool:
    return abs(a - b) <= max(abs_tol, abs(b) * rel)


def _fmt(n: float) -> str:
    """Human-readable number (commas, no scientific notation)."""
    return f"{int(n):,}" if float(n).is_integer() else f"{n:,.2f}"


def check_percentage_claims(text: str) -> List[str]:
    """Verify explicit 'X% of Y is/= Z' statements."""
    issues: List[str] = []
    pattern = re.compile(r"(\d[\d.,]*)\s*%\s*of\s*\$?(\d[\d.,]*)\s*(?:is|=|equals?|→|->)\s*\$?(\d[\d.,]*)", re.I)
    for m in pattern.finditer(text or ""):
        pct, base, claimed = (_to_float(g) for g in m.groups())
        if None in (pct, base, claimed):
            continue
        expected = round(base * pct / 100.0, 2)
        if not _close(claimed, expected):
            issues.append(f"{pct:g}% of {_fmt(base)} is {_fmt(expected)}, not {_fmt(claimed)}")
    return issues


def find_calculation_issues(text: str) -> List[str]:
    return check_percentage_claims(text)


# --- framework / semantic guardrails -------------------------------------

PORTER_FORCES = (
    "competitive rivalry", "threat of new entrants", "bargaining power of buyers",
    "bargaining power of suppliers", "threat of substitutes",
)
_PORTER_CONTEXT = ("porter", "five forces", "5 forces", "lima kekuatan")
_PORTER_INVALID = (
    "pengadilan", "court", "judge", "lawsuit", "litigation", "regulator",
    "government", "pemerintah", "weather", "macroeconomic",
)


def mentions_porter(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in _PORTER_CONTEXT)


def validate_porter(text: str) -> List[str]:
    """Flag invalid 'forces' (e.g. courts/pengadilan) when Porter is discussed."""
    if not mentions_porter(text):
        return []
    low = (text or "").lower()
    return [f"'{bad}' is not one of Porter's Five Forces" for bad in _PORTER_INVALID if bad in low]


_INBOUND_ACQ = (
    "offers to acquire", "offer to acquire", "wants to acquire", "wants to buy us",
    "wants to buy you", "acquisition offer", "bid to acquire", "to acquire us",
    "to acquire you", "menawarkan untuk mengakuisisi", "ingin mengakuisisi", "ingin membeli",
)
_OUTBOUND_ACQ = (
    "you acquire", "we acquire", "you should acquire", "we should acquire",
    "you buy them", "acquiring them", "you are acquiring", "mengakuisisi mereka",
    "membeli mereka",
)


def check_acquisition_direction(user_text: str, answer_text: str) -> List[str]:
    """Catch a reversed acquisition: an inbound offer misread as the user acquiring."""
    u, a = (user_text or "").lower(), (answer_text or "").lower()
    if any(k in u for k in _INBOUND_ACQ) and any(k in a for k in _OUTBOUND_ACQ):
        return ["acquisition direction reversed: the user is the acquisition target, "
                "but the answer frames the user as the acquirer"]
    return []


# --- no-op replies ---------------------------------------------------------

# A reply that only acknowledges ("completed", "done", "selesai") carries no
# information — after tool activity it must be replaced with a real summary.
_NOOP_REPLY_RE = re.compile(
    r"^\s*(?:task\s+)?(?:completed?|done|finish(?:ed)?|selesai|sukses|success|"
    r"berhasil|ok(?:e|ay)?|sip)[\s!.]*$",
    re.IGNORECASE,
)


def is_noop_reply(text: str) -> bool:
    """True when a reply is a bare acknowledgement with no actual content."""
    return bool(_NOOP_REPLY_RE.match(text or ""))


# --- relevance / grounding / scoring -------------------------------------

_WORD = re.compile(r"[a-zA-Z]{4,}")


def _keywords(text: str) -> set:
    return {w.lower() for w in _WORD.findall(text or "")}


def input_relevance(user_text: str, answer: str) -> float:
    """Coverage of the user's key terms by the answer (0..1)."""
    u, a = _keywords(user_text), _keywords(answer)
    if not u:
        return 1.0 if a else 0.0
    if not a:
        return 0.0
    return round(len(u & a) / len(u), 3)


def grounding_score(user_text: str, answer: str) -> float:
    ans_nums = _nums(answer)
    if not ans_nums:
        return input_relevance(user_text, answer)
    in_nums = _nums(user_text)
    has_assumption = bool(extract_assumptions(answer))

    def derivable(n: float) -> bool:
        if any(_close(n, i) for i in in_nums):
            return True
        for i in in_nums:
            for j in in_nums:
                cands = [i * j, i + j, i - j, i * j / 100.0]
                if j:
                    cands.append(i / j)
                if any(_close(n, round(c, 2)) for c in cands):
                    return True
        return False

    grounded = sum(1 for n in ans_nums if derivable(n))
    base = grounded / len(ans_nums)
    if has_assumption:
        base = max(base, 0.6)  # honestly labeled assumptions raise the floor
    return round(base, 3)


def calculation_check_score(answer: str) -> float:
    issues = find_calculation_issues(answer)
    return 1.0 if not issues else round(max(0.0, 1.0 - 0.34 * len(issues)), 3)


def hallucination_risk(user_text: str, answer: str) -> float:
    risk = 0.0
    if validate_porter(answer):
        risk += 0.5
    if check_acquisition_direction(user_text, answer):
        risk += 0.5
    risk += (1.0 - grounding_score(user_text, answer)) * 0.3
    return round(min(1.0, risk), 3)


@dataclass
class ReasoningScore:
    input_relevance: float
    grounding: float
    calculation_check: float
    hallucination_risk: float
    final_answer_confidence: float
    issues: List[str] = field(default_factory=list)

    def is_low(self, threshold: float = 0.55) -> bool:
        return self.final_answer_confidence < threshold or self.hallucination_risk >= 0.5

    def to_meta(self) -> dict:
        return {
            "input_relevance_score": self.input_relevance,
            "grounding_score": self.grounding,
            "calculation_check_score": self.calculation_check,
            "hallucination_risk": self.hallucination_risk,
            "final_answer_confidence": self.final_answer_confidence,
            "issues": self.issues,
        }


def score_response(user_text: str, answer: str) -> ReasoningScore:
    rel = input_relevance(user_text, answer)
    gr = grounding_score(user_text, answer)
    calc = calculation_check_score(answer)
    risk = hallucination_risk(user_text, answer)
    conf = round(max(0.0, min(1.0, 0.3 * rel + 0.3 * gr + 0.2 * calc + 0.2 * (1.0 - risk))), 3)
    issues: List[str] = []
    issues += find_calculation_issues(answer)
    issues += validate_porter(answer)
    issues += check_acquisition_direction(user_text, answer)
    return ReasoningScore(rel, gr, calc, risk, conf, issues)


def assess_critique(critique: str, user_text: str, analyst_answer: str) -> dict:
    """Decide whether a Critic's critique is relevant enough to act on.

    Lets the Synthesizer reject irrelevant/hallucinated criticism (e.g. inventing
    'pengadilan' as a Porter force) instead of blindly accepting it.
    """
    reasons: List[str] = []
    if validate_porter(critique):
        reasons.append("introduces invalid Porter forces")
    relevance = input_relevance(f"{user_text} {analyst_answer}", critique)
    if relevance < 0.12:
        reasons.append("largely unrelated to the question or analysis")
    return {"relevant": not reasons, "relevance": relevance, "reasons": reasons}


def reasoning_summary(user_text: str, answer: str, score: ReasoningScore, task_type: str) -> str:
    """A concise, user-facing reasoning summary — NOT hidden chain-of-thought.

    Built deterministically from grounding/verification, so it never leaks the
    model's internal step-by-step reasoning.
    """
    facts = extract_facts(user_text)
    assumptions = extract_assumptions(answer)
    parts: List[str] = [f"Task: {task_type}."]
    if facts["numbers"]:
        parts.append("Key inputs: " + ", ".join(facts["numbers"][:6]) + ".")
    if assumptions:
        parts.append("Assumptions: " + "; ".join(assumptions[:3]) + ".")
    checks = ["calculations verified" if score.calculation_check >= 0.999 else "calculation issues found"]
    if mentions_porter(user_text + " " + answer):
        checks.append("Porter forces valid" if not validate_porter(answer) else "invalid Porter force flagged")
    parts.append("Checks: " + ", ".join(checks) + ".")
    parts.append(f"Confidence: {int(round(score.final_answer_confidence * 100))}%.")
    if score.issues:
        parts.append("Flags: " + "; ".join(score.issues[:3]) + ".")
    return " ".join(parts)
