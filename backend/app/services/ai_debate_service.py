"""Multi-agent debate: 2–3 agents argue across rounds, then one synthesizes.

How it differs from ``ai_multi_service`` (parallel fan-out):
    * Round 1 (opening): every runnable agent answers the question independently.
    * Rounds 2..N (rebuttal): each agent is shown the *other* agents' latest
      answers and asked to critique, defend, and refine — this is the "debate".
    * Synthesis: the first selected runnable agent reads the whole transcript and
      produces a single best final answer.

Safety / honesty (same guarantees as the parallel path):
    * All DB access happens on the request thread; only the provider network call
      runs in a worker thread (the SQLAlchemy session is never shared).
    * One agent failing never fails the others; each result is captured and
      persisted honestly. Non-runnable agents (blocked/not_configured/disabled)
      are recorded with their real status — never faked.
    * A real debate needs >= 2 runnable agents. With exactly one, we return that
      agent's answer (no fabricated debate); with none, the run is an honest error.
    * No agent executes writes; this only routes chat and persists results.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.ai import (
    MAX_AGENTS_PER_RUN,
    AiAgentResponse,
    AiMultiAgentRun,
    ChatMessage,
    ChatSession,
)
from app.services import ai_provider_router
from app.services.ai_multi_service import (
    AGENT_TIMEOUT_SECONDS,
    UNSUPPORTED_IMAGE_MSG,
    _dedup,
    _run_one,
    _user_meta,
)
from app.services.ai_provider_router import ChatPlan
from app.services.ai_service import _auto_title
from app.services.thinking import thinking_params

# Number of debate rounds (round 1 opening + rebuttal rounds). Bounded so a run
# never explodes into too many provider calls (3 agents x 4 rounds + synthesis).
DEFAULT_DEBATE_ROUNDS = 2
MAX_DEBATE_ROUNDS = 4


# --- prompt builders ------------------------------------------------------


def _opening_prompt(agent_name: str, n_agents: int, question: str) -> str:
    return (
        f'You are "{agent_name}", one of {n_agents} AI agents on a panel answering the '
        f"same question.\n\nQUESTION:\n{question}\n\n"
        "Give your best, well-reasoned initial answer. Be substantive but concise. You will "
        "later see the other agents' answers and get a chance to refine yours."
    )


def _rebuttal_prompt(agent_name: str, question: str, others: List[Tuple[str, str]]) -> str:
    blocks = "\n\n".join(f"--- {name} answered ---\n{content}" for name, content in others)
    return (
        f'You are "{agent_name}" in a multi-agent debate about this QUESTION:\n{question}\n\n'
        f"Here are the other agents' latest answers:\n\n{blocks}\n\n"
        "Critically evaluate their answers and your own: point out errors or gaps, defend or "
        "revise your position with reasons, then give your improved answer. If another agent "
        "made a better point, adopt it. Be concise and focus on getting the answer right."
    )


def _synthesis_prompt(question: str, transcript: List[Tuple[str, List[Tuple[str, str]]]]) -> str:
    parts: List[str] = []
    for label, entries in transcript:
        parts.append(f"## {label}")
        for name, content in entries:
            parts.append(f"### {name}\n{content}")
    body = "\n\n".join(parts)
    return (
        "You are the moderator of a panel debate among AI agents. Read the full debate below and "
        "produce the single best final answer for the user.\n\n"
        f"QUESTION:\n{question}\n\nDEBATE TRANSCRIPT:\n{body}\n\n"
        "Write the final answer with these rules:\n"
        "1. Start with the direct answer/decision — no preamble.\n"
        "2. Integrate the agents' best points; remove contradictions, repetition, and rambling — "
        "but PRESERVE important warnings, risks, and security concerns.\n"
        "3. Be concrete and specific (exact names, numbers, steps); never generic.\n"
        "4. When agents disagree on something that matters, pick a position and say why in one "
        "line — do not just list options.\n"
        "5. Be honest about uncertainty and missing data; never invent facts the debate "
        "doesn't support.\n"
        "6. End with next steps when the topic is actionable.\n"
        "7. Answer in the user's language (Indonesian question → natural Indonesian answer).\n"
        "Do not mention that you are a moderator or that a debate happened — just give the answer."
    )


# --- concurrent round execution -------------------------------------------


def _run_round(
    runnable: Dict[str, ChatPlan], prompts: Dict[str, str], images: Optional[List[str]] = None,
    params: Optional[dict] = None,
) -> Dict[str, dict]:
    """Run one debate round: every runnable agent's call fans out concurrently."""
    outcomes: Dict[str, dict] = {}
    if not runnable:
        return outcomes
    with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
        futures = {
            pool.submit(_run_one, plan, [{"role": "user", "content": prompts[pid], "images": images or []}], params, bool(images)): pid
            for pid, plan in runnable.items()
        }
        for future, pid in list(futures.items()):
            try:
                outcomes[pid] = future.result(timeout=AGENT_TIMEOUT_SECONDS)
            except FutureTimeout:
                outcomes[pid] = {
                    "status": "error", "content": None,
                    "error": "the agent timed out", "latency_ms": int(AGENT_TIMEOUT_SECONDS * 1000),
                }
    return outcomes


def debate_chat(
    db: Session,
    principal: Principal,
    *,
    message: str,
    provider_ids: List[str],
    session_id: Optional[uuid.UUID] = None,
    rounds: int = DEFAULT_DEBATE_ROUNDS,
    images: Optional[List[str]] = None,
    thinking_mode: str = "balance",
    section_key: Optional[str] = "general",
) -> dict:
    from app.services import memory_context_builder, memory_extraction_service

    ids = _dedup(provider_ids)
    if not ids:
        raise ValidationAppError("Select at least one AI agent.")
    if len(ids) > MAX_AGENTS_PER_RUN:
        raise ValidationAppError(f"Maximum {MAX_AGENTS_PER_RUN} agents per run.")
    rounds = max(1, min(int(rounds or DEFAULT_DEBATE_ROUNDS), MAX_DEBATE_ROUNDS))

    # Session + user message (persisted regardless of agent outcomes).
    if session_id is not None:
        session = db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.workspace_id == principal.workspace_id,
            )
        )
        if not session:
            raise NotFoundError("Chat session not found.")
    else:
        session = ChatSession(
            workspace_id=principal.workspace_id,
            created_by=principal.user_id,
            title=_auto_title(message),
        )
        db.add(session)
        db.flush()
    if not (session.title or "").strip():
        session.title = _auto_title(message)

    user_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="user",
        content=message,
        meta=_user_meta("debate", thinking_mode, images),
    )
    db.add(user_message)
    db.flush()

    run = AiMultiAgentRun(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        user_message_id=user_message.id,
        provider_ids=ids,
        status="running",
        created_by=principal.user_id,
    )
    db.add(run)
    db.flush()

    # Resolve every provider on this thread (DB reads only).
    plans = {pid: ai_provider_router.plan_chat(db, principal, pid) for pid in ids}
    runnable = {pid: p for pid, p in plans.items() if p.runnable}
    # With an image attached, only vision-capable agents can join the debate.
    has_images = bool(images)
    if has_images:
        runnable = {pid: p for pid, p in runnable.items() if p.supports_image}
    n_runnable = len(runnable)
    params = thinking_params(thinking_mode)

    responses: List[AiAgentResponse] = []

    def _record(
        provider_id: str, provider_name: str, status: str, content: Optional[str],
        error: Optional[str], latency: Optional[int], external: bool,
        *, round_no: Optional[int], phase: str,
    ) -> None:
        """Persist one agent turn as both an AiAgentResponse row and a ChatMessage."""
        row = AiAgentResponse(
            workspace_id=principal.workspace_id,
            run_id=run.id,
            provider_id=provider_id,
            provider_name=provider_name,
            status=status,
            content=content,
            error_message=error,
            latency_ms=latency,
            meta={"external": external, "round": round_no, "phase": phase},
        )
        db.add(row)
        responses.append(row)
        db.add(
            ChatMessage(
                workspace_id=principal.workspace_id,
                session_id=session.id,
                role="assistant",
                content=content if status == "completed" and content else (error or status),
                meta={
                    "provider_id": provider_id,
                    "provider_name": provider_name,
                    "status": status,
                    "run_id": str(run.id),
                    "latency_ms": latency,
                    "external": external,
                    "debate": True,
                    "round": round_no,
                    "phase": phase,
                },
            )
        )

    # Non-runnable agents: record their honest status once (as part of round 1) so
    # the user sees exactly why an agent can't join the debate.
    for pid in ids:
        plan = plans[pid]
        if pid in runnable:
            continue
        if has_images and plan.runnable and not plan.supports_image:
            status, msg = "unsupported", UNSUPPORTED_IMAGE_MSG
        else:
            status = plan.status if plan.status in ("blocked", "not_configured", "disabled") else "error"
            msg = plan.message
        _record(pid, plan.provider_name, status, None, msg, None, plan.external,
                round_no=1, phase="opening")

    # No runnable agents -> honest error, no fabricated debate.
    if n_runnable == 0:
        run.status = "error"
        final_msg = ChatMessage(
            workspace_id=principal.workspace_id,
            session_id=session.id,
            role="assistant",
            content=(
                "No selected agent could run, so there is nothing to debate. Configure and enable "
                "at least two AI agents in Settings → AI Providers (and allow external AI if needed)."
            ),
            meta={"provider_name": "Debate", "status": "error", "run_id": str(run.id),
                  "debate": True, "debate_final": True},
        )
        db.add(final_msg)
        db.commit()
        db.refresh(run)
        for r in responses:
            db.refresh(r)
        try:
            memory_extraction_service.schedule_extraction(
                db, principal, message, "", session.id
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        return {"run": run, "session_id": session.id, "responses": responses}

    # --- run the rounds (network calls in worker threads) ---
    round_outcomes: List[Dict[str, dict]] = []
    last_answer: Dict[str, str] = {}  # pid -> most recent completed content
    rounds_to_run = rounds if n_runnable >= 2 else 1  # one agent => no rebuttal

    extra_context = memory_context_builder.build(db, principal, message, section_key)
    # Debate rounds have no system message; prefix the opening user prompt instead.
    mem_prefix = f"{extra_context}\n\n" if extra_context else ""
    for k in range(1, rounds_to_run + 1):
        if k == 1:
            prompts = {
                pid: mem_prefix + _opening_prompt(plans[pid].provider_name, n_runnable, message)
                for pid in runnable
            }
        else:
            # Stop early if the prior round produced nothing to argue about.
            if not last_answer:
                break
            prompts = {}
            for pid in runnable:
                others = [
                    (plans[o].provider_name, last_answer[o])
                    for o in runnable if o != pid and o in last_answer
                ]
                prompts[pid] = _rebuttal_prompt(plans[pid].provider_name, message, others)
        outcomes = _run_round(runnable, prompts, images if k == 1 else None, params)
        round_outcomes.append(outcomes)
        for pid, oc in outcomes.items():
            if oc["status"] == "completed" and oc["content"]:
                last_answer[pid] = oc["content"]

    # Persist every round turn in selection + round order.
    round_errors = 0
    for idx, outcomes in enumerate(round_outcomes, start=1):
        phase = "opening" if idx == 1 else "rebuttal"
        for pid in ids:
            if pid not in outcomes:
                continue
            oc = outcomes[pid]
            if oc["status"] != "completed":
                round_errors += 1
            _record(pid, plans[pid].provider_name, oc["status"], oc["content"], oc["error"],
                    oc["latency_ms"], plans[pid].external, round_no=idx, phase=phase)

    # --- synthesis ---
    synth_pid = next((pid for pid in ids if pid in runnable), None)
    transcript: List[Tuple[str, List[Tuple[str, str]]]] = []
    for idx, outcomes in enumerate(round_outcomes, start=1):
        label = "Opening" if idx == 1 else f"Round {idx}"
        entries = [
            (plans[pid].provider_name, outcomes[pid]["content"])
            for pid in ids
            if pid in outcomes and outcomes[pid]["status"] == "completed" and outcomes[pid]["content"]
        ]
        if entries:
            transcript.append((label, entries))

    final_status, final_content, final_error, final_latency = "error", None, None, None
    if not transcript:
        final_error = "No agent produced an answer, so there was nothing to synthesize."
    elif n_runnable == 1:
        # One agent: its answer is the result (no fabricated debate/synthesis call).
        final_status, final_content = "completed", last_answer.get(synth_pid)
        if not final_content:
            final_status, final_content, final_error = "error", None, "The agent did not produce an answer."
    else:
        oc = _run_round({synth_pid: runnable[synth_pid]},
                        {synth_pid: _synthesis_prompt(message, transcript)}, None, params)[synth_pid]
        final_status = oc["status"]
        final_content = oc["content"]
        final_error = oc["error"]
        final_latency = oc["latency_ms"]

    synth_name = plans[synth_pid].provider_name if synth_pid else "Debate"
    synth_external = plans[synth_pid].external if synth_pid else False
    synth_row = AiAgentResponse(
        workspace_id=principal.workspace_id,
        run_id=run.id,
        provider_id=synth_pid or "debate",
        provider_name=synth_name,
        status=final_status,
        content=final_content,
        error_message=final_error,
        latency_ms=final_latency,
        meta={"external": synth_external, "phase": "synthesis"},
    )
    db.add(synth_row)
    responses.append(synth_row)
    db.add(
        ChatMessage(
            workspace_id=principal.workspace_id,
            session_id=session.id,
            role="assistant",
            content=final_content if final_status == "completed" and final_content else (final_error or final_status),
            meta={
                "provider_id": synth_pid or "debate",
                "provider_name": synth_name,
                "status": final_status,
                "run_id": str(run.id),
                "latency_ms": final_latency,
                "external": synth_external,
                "debate": True,
                "debate_final": True,
                "rounds": len(round_outcomes),
                "n_agents": n_runnable,
            },
        )
    )

    if final_status == "completed":
        run.status = "completed" if round_errors == 0 else "partial"
    else:
        run.status = "error"

    db.flush()
    db.commit()
    db.refresh(run)
    for r in responses:
        db.refresh(r)

    # Trigger hybrid memory extraction using the synthesis content as the assistant reply.
    try:
        memory_extraction_service.schedule_extraction(
            db, principal, message, final_content or "", session.id
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    return {"run": run, "session_id": session.id, "responses": responses}
