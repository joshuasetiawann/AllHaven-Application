"""Regression tests for the AI response-quality fixes (v4.x).

Covers the user-reported bugs:
- the AI sometimes replied with the literal status word "completed" (or a blank bubble)
  instead of a real answer;
- a genuine question that merely mentions money/schedule was hijacked into a canned
  finance/schedule draft instead of getting a real, conversational answer.
"""
from app.services import ai_intent_router as router
from app.services.ai_reply_text import display_text


# --------------------------- display_text helper --------------------------- #

def test_display_text_never_returns_status_sentinel():
    # An agent that "completed" but produced no text must NOT show the word "completed".
    out = display_text("completed", "", None)
    assert out and out.lower() != "completed"
    assert "completed" not in out.lower()

    out_none = display_text("completed", None, None)
    assert out_none and out_none.lower() != "completed"

    # The literal sentinel arriving as content is also masked.
    assert display_text("completed", "completed", None).lower() != "completed"


def test_display_text_returns_real_prose_unchanged():
    real = "Tentu, ini penjelasannya: REST adalah gaya arsitektur untuk API."
    assert display_text("completed", real, None) == real


def test_display_text_prefers_error_over_status():
    out = display_text("error", "", "Provider OpenAI tidak bisa dihubungi.")
    assert out == "Provider OpenAI tidak bisa dihubungi."


def test_display_text_status_specific_fallbacks():
    assert "AI Providers" in display_text("not_configured", "", None)
    assert "Privacy" in display_text("blocked", "", None)
    # Unknown status still yields a friendly, non-empty, non-sentinel sentence.
    generic = display_text("weird_status", "", None)
    assert generic and generic.lower() not in ("weird_status", "completed", "")


# ----------------------- is_question / finance hijack ---------------------- #

def test_question_with_amount_is_not_finance():
    # Advice request that mentions a price must reach the LLM, not a canned draft.
    res = router.classify("menurut kamu worth ga beli laptop 15 juta?")
    assert res.intent != router.FINANCE

    res2 = router.classify("mendingan beli mobil 200 juta atau nabung?")
    assert res2.intent != router.FINANCE


def test_real_recording_command_still_finance():
    # The deterministic recording path must keep working.
    assert router.classify("catat pengeluaran makan 50 ribu").intent == router.FINANCE
    assert router.classify("saya dapat pendapatan 500 ribu").intent == router.FINANCE
    assert router.classify("gaji 5000000").intent == router.FINANCE


def test_is_question_predicate():
    assert router.is_question("worth ga beli laptop 15 juta?") is True
    assert router.is_question("berapa total pengeluaran bulan ini?") is True
    assert router.is_question("bagaimana caranya hemat uang") is True
    assert router.is_question("catat pengeluaran makan 50 ribu") is False
    assert router.is_question("gaji 5 juta") is False
