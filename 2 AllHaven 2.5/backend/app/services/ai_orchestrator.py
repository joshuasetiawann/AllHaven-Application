"""AI orchestrator — single-agent chat with a safe, audited tool loop.

Flow per user message:
    1. Resolve the provider plan (honest statuses; no fake output).
    2. Load recent conversation history (small, workspace-scoped).
    3. If the provider supports native tool calling (OpenAI-compatible family):
       loop — model may request tools; each request is validated and run through
       the Tool Registry. Reads execute; writes become PENDING proposals. Tool
       results are fed back until the model produces a final text answer.
    4. Providers without tool support chat normally (with history) — honest:
       no tools are claimed for them.

The model NEVER touches the DB/shell/files directly — only registry outcomes.
"""

from __future__ import annotations

import json
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.ai import ChatMessage
from app.services import ai_provider_router, ai_tools_registry

MAX_TOOL_ROUNDS = 5
HISTORY_MESSAGES = 12
HISTORY_CHAR_LIMIT = 4000

SYSTEM_PROMPT = (
    "You are Haven, the AI assistant inside the AllHaven Command Center — the user's "
    "private workspace for tasks, notes, calendar, finance, files, weather, automations, "
    "and system control.\n"
    "Tool rules (strict):\n"
    "  * Use tools to answer questions about the user's real data; never invent data.\n"
    "  * A tool outcome with status 'pending_approval' means the action was NOT executed — "
    "it awaits HUMAN approval. Say so clearly; never claim it was done.\n"
    "  * If a tool returns an error or 'setup_required', tell the user honestly and "
    "suggest the fix (e.g. configure the provider in Settings).\n"
    "Answer style: start with the direct answer; be specific and concrete; no generic "
    "filler or repeated caveats; use short sections or lists only when they help; say "
    "what is missing when data is missing; reply in the user's language (Bahasa Indonesia "
    "in, Bahasa Indonesia out)."
)


def _recent_history(db: Session, principal: Principal, session_id: Optional[uuid.UUID]) -> List[dict]:
    """Last few turns as plain {role, content} (user/assistant only)."""
    if session_id is None:
        return []
    rows = list(db.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.workspace_id == principal.workspace_id,
            ChatMessage.session_id == session_id,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_MESSAGES)
    ).all())
    rows.reverse()
    history: List[dict] = []
    for m in rows:
        if m.role in ("user", "assistant") and (m.content or "").strip():
            history.append({"role": m.role, "content": m.content[:HISTORY_CHAR_LIMIT]})
    return history


def _tool_summary(outcome: dict) -> str:
    status = outcome.get("status")
    if status == "executed":
        return "done"
    if status == "pending_approval":
        return f"awaiting approval ({outcome.get('risk', '')})".strip()
    return (outcome.get("error") or "failed")[:140]


def run_with_tools(
    db: Session,
    principal: Principal,
    *,
    message: str,
    session_id: Optional[uuid.UUID] = None,
    provider_id: Optional[str] = None,
) -> dict:
    """Route one chat turn, with the tool loop when the provider supports it.

    Returns the same shape as ``ai_provider_router.run_chat`` plus
    ``tool_calls`` (activity meta) and ``proposal_ids`` (pending approvals).
    """
    plan = ai_provider_router.plan_chat(db, principal, provider_id)
    pid = plan.provider_id
    base = {"provider_id": pid, "tool_calls": [], "proposal_ids": []}
    if plan.status == "error" and not plan.runnable and plan.provider_name == pid:
        return {**base, "ok": False, "configured": False, "blocked": False,
                "content": plan.message, "error": "unknown_provider"}
    if plan.status == "blocked":
        return {**base, "ok": False, "configured": plan.configured, "blocked": True,
                "content": plan.message, "error": "external_disabled"}
    if plan.status == "not_configured":
        return {**base, "ok": False, "configured": False, "blocked": False,
                "content": plan.message, "error": "not_configured"}
    if plan.status == "disabled":
        return {**base, "ok": False, "configured": True, "blocked": False,
                "content": plan.message, "error": "disabled"}

    history = _recent_history(db, principal, session_id)
    user_turn = {"role": "user", "content": message}

    if not plan.supports_tool_loop:
        # Honest non-tool path (Ollama/Anthropic/Gemini/Blackbox today): plain chat
        # with history; we never pretend tools ran.
        result = plan.execute([*history, user_turn])
        if result.ok:
            return {**base, "ok": True, "configured": True, "blocked": False,
                    "content": result.content, "error": ""}
        return {**base, "ok": False, "configured": True, "blocked": False,
                "content": f"The '{plan.provider_name}' provider could not complete the request: {result.error}",
                "error": result.error}

    tools = ai_tools_registry.tool_definitions(db, principal)
    convo: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, *history, user_turn]
    tool_meta: List[dict] = []
    proposal_ids: List[str] = []
    result = None

    for round_no in range(MAX_TOOL_ROUNDS):
        result = plan.execute(convo, None, tools or None)
        if not result.ok or not result.tool_calls:
            break
        # Echo the assistant tool request, then answer each call via the registry.
        convo.append({
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": [
                {"id": tc["id"] or f"call_{round_no}_{i}", "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for i, tc in enumerate(result.tool_calls)
            ],
        })
        for i, tc in enumerate(result.tool_calls):
            try:
                args = json.loads(tc["arguments"] or "{}")
            except (ValueError, TypeError):
                args = None
            if isinstance(args, dict):
                outcome = ai_tools_registry.run_tool_call(db, principal, tc["name"], args)
            else:
                outcome = {"status": "error", "tool": tc["name"],
                           "error": "tool arguments were not valid JSON"}
            if outcome.get("status") == "pending_approval" and outcome.get("proposal_id"):
                proposal_ids.append(outcome["proposal_id"])
            tool_meta.append({"tool": tc["name"], "status": outcome.get("status", "error"),
                              "summary": _tool_summary(outcome)})
            convo.append({
                "role": "tool",
                "tool_call_id": tc["id"] or f"call_{round_no}_{i}",
                "content": json.dumps(outcome, default=str)[:6000],
            })
    else:
        # Round budget exhausted while the model still wanted tools: force a
        # final text answer without tools so the user gets a real reply.
        result = plan.execute(convo)

    base = {"provider_id": pid, "tool_calls": tool_meta, "proposal_ids": proposal_ids}
    if result is not None and result.ok:
        content = result.content
        if not (content or "").strip() and tool_meta:
            content = "I ran the requested tools — see the activity above."
        return {**base, "ok": True, "configured": True, "blocked": False,
                "content": content, "error": ""}
    error = result.error if result is not None else "no response"
    return {**base, "ok": False, "configured": True, "blocked": False,
            "content": f"The '{plan.provider_name}' provider could not complete the request: {error}",
            "error": error}
