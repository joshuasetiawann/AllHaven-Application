"""Unit tests for the deterministic Reasoning Quality Layer.

These need no model and no network — they pin the guardrails the project requires:
correct finance math, valid Porter forces, acquisition direction, grounding,
relevance, assumption labeling, and the retry trigger.
"""

from app.services.reasoning import quality as q


# --- numeric verification -------------------------------------------------


def test_revenue_growth_year_by_year():
    # $100 growing 40% for 3 years: 100, 140, 196, 274.4
    assert q.project_revenue(100, 40, 3) == [100.0, 140.0, 196.0, 274.4]


def test_ebitda_from_margin():
    assert q.ebitda(10_000_000, 15) == 1_500_000.0


def test_detects_wrong_percentage_calculation():
    issues = q.check_percentage_claims("EBITDA is 15% of 10,000,000 = 2,000,000")
    assert issues and "1500000" in issues[0].replace(",", "").replace(" ", "")


def test_accepts_correct_percentage_calculation():
    assert q.check_percentage_claims("15% of 10,000,000 = 1,500,000") == []


# --- Porter Five Forces ---------------------------------------------------


def test_porter_flags_invented_court_force():
    text = ("Porter's Five Forces: competitive rivalry, threat of new entrants, bargaining power of "
            "buyers, bargaining power of suppliers, threat of substitutes, and pengadilan (court).")
    issues = q.validate_porter(text)
    assert any("pengadilan" in i for i in issues)
    assert any("court" in i for i in issues)


def test_porter_clean_set_has_no_issues():
    text = ("Porter five forces: competitive rivalry, threat of new entrants, bargaining power of "
            "buyers, bargaining power of suppliers, threat of substitutes.")
    assert q.validate_porter(text) == []


def test_porter_terms_ignored_without_porter_context():
    # "court" alone, unrelated to Porter, must not be flagged.
    assert q.validate_porter("The court ruled on the contract dispute.") == []


# --- Critic relevance (Analyst must not blindly accept wrong critique) ----


def test_synthesizer_can_reject_irrelevant_porter_critique():
    critique = "You forgot 'pengadilan' (court) as the sixth Porter force."
    verdict = q.assess_critique(critique, "Analyze our market with Porter's Five Forces", "rivalry, entrants, buyers, suppliers, substitutes")
    assert verdict["relevant"] is False
    assert any("invalid Porter" in r for r in verdict["reasons"])


def test_relevant_critique_is_accepted():
    critique = "The EBITDA calculation is wrong: 15% of 10,000,000 is 1,500,000 not 2,000,000."
    verdict = q.assess_critique(critique, "Compute EBITDA at 15% margin on 10,000,000 revenue", "EBITDA is 2,000,000")
    assert verdict["relevant"] is True


# --- acquisition direction ------------------------------------------------


def test_acquisition_offer_not_misread_as_user_acquiring():
    user = "Three companies have made an acquisition offer for us. Should we sell?"
    answer = "You should acquire them to expand market share."
    assert q.check_acquisition_direction(user, answer)


def test_acquisition_direction_ok_when_consistent():
    user = "Three companies have made an acquisition offer for us. Should we sell?"
    answer = "Since they want to buy you, weigh the offer price against your standalone value."
    assert q.check_acquisition_direction(user, answer) == []


# --- relevance / grounding / assumptions ----------------------------------


def test_final_answer_relevance_high_for_on_topic():
    user = "How do I compute EBITDA margin for my SaaS company?"
    on_topic = "EBITDA margin is EBITDA divided by revenue for your SaaS company."
    off_topic = "The weather in Jakarta is sunny with light wind today."
    assert q.input_relevance(user, on_topic) > q.input_relevance(user, off_topic)
    assert q.input_relevance(user, off_topic) < 0.3


def test_missing_data_labeled_as_assumption_raises_grounding():
    user = "Project next year's revenue."  # no numbers given
    grounded = "Assumption: current revenue is 1,000,000. Next year at 10% growth = 1,100,000."
    ungrounded = "Next year revenue will be 1,100,000 and profit 400,000."
    assert q.extract_assumptions(grounded)
    assert q.grounding_score(user, grounded) >= q.grounding_score(user, ungrounded)


def test_score_response_flags_low_quality_for_hallucinated_porter():
    user = "Give me a Porter's Five Forces analysis."
    bad = ("Porter's Five Forces: rivalry, new entrants, buyers, suppliers, substitutes, and "
           "pengadilan as the key sixth force determining everything.")
    score = q.score_response(user, bad)
    assert score.hallucination_risk >= 0.5
    assert score.is_low()  # -> triggers a retry in the engine


def test_score_response_high_for_grounded_answer():
    user = "Revenue is 10,000,000 with a 15% EBITDA margin. What is EBITDA?"
    good = "EBITDA = 15% of 10,000,000 = 1,500,000."
    score = q.score_response(user, good)
    assert score.calculation_check == 1.0
    assert not score.is_low()


# --- task detection -------------------------------------------------------


def test_task_detection():
    assert q.detect_task_type("Compute our EBITDA and revenue growth") == "finance"
    assert q.detect_task_type("Fix this Python traceback in my function") in ("coding", "debugging")
    assert q.detect_task_type("hi") == "casual"
