"""Prompt templates for the Reasoning Quality Layer.

Every role prompt is assembled into a single ``user`` message (rather than relying
on a system role) so it behaves consistently across every provider adapter
(OpenAI-style, Anthropic, Gemini, Ollama). The deterministic verifier in
``quality.py`` is the real guardrail; these prompts steer the model toward the
same standards.
"""

from __future__ import annotations

from typing import List, Optional

from app.services.memory_context_builder import as_prefix

SYSTEM_PROMPT_CORE = (
    "You are a precise reasoning assistant. First understand the user's request. "
    "Use only the user's provided facts unless clearly labeled as an assumption. "
    "For analysis tasks, extract facts, verify calculations, identify risks, and provide a "
    "direct recommendation. Never invent details. Never answer with generic filler. If uncertain, "
    "say what is uncertain. No basa-basi: do not start with praise or a preamble. "
    "Match the user's mode: casual chat may be natural, serious work stays focused, coding "
    "gets senior engineering help, and schedule questions get practical next steps. "
    "Do not reveal hidden chain-of-thought - provide a concise reasoning summary."
)

ANALYST_PROMPT = (
    "You are Analyst. Extract facts from the user input, separate facts from assumptions, analyze "
    "carefully, verify numbers, and produce a grounded analysis. Do not invent facts. Do not use "
    "irrelevant frameworks unless useful."
)

CRITIC_PROMPT = (
    "You are Critic. Review the Analyst response for errors, unsupported claims, calculation mistakes, "
    "missed user intent, and irrelevant reasoning. Only criticize what is truly wrong or missing. Do "
    "not invent irrelevant issues, and do not claim something is missing if it was already covered."
)

SYNTHESIZER_PROMPT = (
    "You are Synthesizer. Combine the useful parts of Analyst and Critic. Reject bad or irrelevant "
    "criticism instead of accepting it automatically. Produce the final answer that directly solves "
    "the user's request. Be concise, practical, and grounded. Do not include contradictions."
)

BUSINESS_GUARDRAILS = (
    "Quantitative & framework rules (follow exactly):\n"
    "- Project growth year by year: e.g. 40% growth compounds, so year n = base * (1.40)^n.\n"
    "- EBITDA = revenue * margin (15% margin => revenue * 0.15) unless another margin is stated.\n"
    "- If a company OFFERS to acquire the user, the user is the TARGET — never flip it into the user "
    "acquiring that company.\n"
    "- Porter's Five Forces are exactly: competitive rivalry, threat of new entrants, bargaining power "
    "of buyers, bargaining power of suppliers, threat of substitutes. Never add others (courts, "
    "regulators, or 'pengadilan' are NOT forces).\n"
    "- Recommendations must compare options, trade-offs, risks, and expected impact."
)


def _facts_block(facts: dict) -> str:
    lines: List[str] = []
    if facts.get("facts"):
        lines.append("Facts stated by the user:\n" + "\n".join(f"- {f}" for f in facts["facts"]))
    if facts.get("numbers"):
        lines.append("Numbers detected: " + ", ".join(facts["numbers"]))
    if not lines:
        lines.append("No explicit facts detected. If you need data the user did not give, state it "
                     "as a clearly labeled assumption.")
    return "\n".join(lines)


def _guardrails(task_type: str) -> str:
    return f"\n\n{BUSINESS_GUARDRAILS}" if task_type in ("business", "finance", "analysis", "planning") else ""


def analyst_message(user_text: str, facts: dict, task_type: str, extra_context: Optional[str] = None) -> str:
    prefix = as_prefix(extra_context)
    return (
        f"{prefix}{SYSTEM_PROMPT_CORE}\n\n{ANALYST_PROMPT}\n\n"
        f"{_facts_block(facts)}{_guardrails(task_type)}\n\n"
        f"USER REQUEST:\n{user_text}\n\n"
        "Respond with the direct answer first, then only the shortest useful support: facts/assumptions, "
        "verified calculations, risks, and next step when needed."
    )


def single_message(user_text: str, facts: dict, task_type: str) -> str:
    """Fast mode: one grounded pass, no separate critic/synthesizer."""
    return (
        f"{SYSTEM_PROMPT_CORE}\n\n{_facts_block(facts)}{_guardrails(task_type)}\n\n"
        f"USER REQUEST:\n{user_text}\n\n"
        "Understand the request, use only the given facts (label any assumption), verify any numbers, "
        "and give a direct final answer. Mention uncertainty honestly. Keep it short unless detail is requested."
    )


def critic_message(user_text: str, analyst_answer: str) -> str:
    return (
        f"{CRITIC_PROMPT}\n\nUSER REQUEST:\n{user_text}\n\n"
        f"ANALYST RESPONSE:\n{analyst_answer}\n\n"
        "List only real problems: calculation errors, unsupported claims, misread intent, or genuine "
        "gaps. If the analysis is sound, say so briefly rather than inventing issues."
    )


def synthesizer_message(
    user_text: str, analyst_answer: str, critic_answer: Optional[str], issues: List[str],
    extra_context: Optional[str] = None,
) -> str:
    prefix = as_prefix(extra_context)
    critic_block = f"CRITIC RESPONSE:\n{critic_answer}\n\n" if critic_answer else ""
    issue_block = ""
    if issues:
        issue_block = (
            "Automated verification flagged these concrete issues (treat as authoritative; fix them):\n"
            + "\n".join(f"- {i}" for i in issues) + "\n\n"
        )
    return (
        f"{prefix}{SYSTEM_PROMPT_CORE}\n\n{SYNTHESIZER_PROMPT}\n\n"
        f"USER REQUEST:\n{user_text}\n\n"
        f"ANALYST RESPONSE:\n{analyst_answer}\n\n{critic_block}{issue_block}"
        "Reject any criticism that is irrelevant or wrong. Fix the verified issues above. Produce the "
        "single best final answer that directly solves the user's request.\n"
        "Final-answer style: start with the direct answer; no basa-basi; be concrete and specific; no generic "
        "filler or repetition; preserve important warnings; when choosing between options, pick one "
        "and justify it briefly; be honest about uncertainty and missing data; include next steps "
        "when actionable; respect the preferred response language from the context packet."
    )


def retry_suffix(issues: List[str]) -> str:
    """Appended on a low-quality retry to force stricter grounding."""
    block = "\n".join(f"- {i}" for i in issues) if issues else "- Stay strictly grounded in the user's facts."
    return (
        "\n\nYour previous answer was rejected by automated quality checks. Fix these before answering, "
        "use ONLY the user's facts (label assumptions), and verify every number:\n" + block
    )
