"""Reasoning council: Analyst -> Critic -> Synthesizer with a quality gate.

This is the high-quality multi-agent path. Unlike the symmetric debate, agents
take distinct roles and every answer is grounded and verified deterministically
(see ``reasoning.quality``):

    * Analyst extracts facts, runs/owns calculations, states assumptions.
    * Critic (Deep mode) reviews the Analyst; its critique is checked for
      relevance so the Synthesizer can REJECT irrelevant/invented criticism
      (e.g. inventing 'pengadilan' as a Porter force) instead of accepting it.
    * Synthesizer produces the final answer, fixing the concrete issues the
      verifier found. If the final answer scores low (irrelevant, ungrounded,
      bad math, reversed acquisition, invalid Porter forces), we retry once with
      stricter grounding; if still low, we return it honestly with its limits.

Reasoning mode (Fast/Balanced/Deep) controls depth and sampling temperature.
Quality scores are persisted in metadata for debugging — never shown as fake
confidence, and the model's hidden chain-of-thought is never stored or returned
(only a concise, deterministic reasoning summary).
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Dict, List, Optional

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
from app.services.reasoning import prompts
from app.services.reasoning import quality as q
from app.services.reasoning.modes import params_for, roles_for
from app.services.thinking import reasoning_depth, thinking_params

ROLE_LABELS = {"analyst": "Analyst", "critic": "Critic", "synthesizer": "Synthesizer"}


def _call(plan: ChatPlan, prompt: str, params: dict, images: Optional[List[str]] = None) -> dict:
    """Run one role's provider call with a hard timeout (network in a worker)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run_one, plan, [{"role": "user", "content": prompt, "images": images or []}], params, bool(images))
        try:
            return fut.result(timeout=AGENT_TIMEOUT_SECONDS)
        except FutureTimeout:
            return {"status": "error", "content": None,
                    "error": "the agent timed out", "latency_ms": int(AGENT_TIMEOUT_SECONDS * 1000)}


def _assign_roles(roles: List[str], runnable_ids: List[str]) -> Dict[str, str]:
    n = len(runnable_ids)
    return {role: runnable_ids[idx % n] for idx, role in enumerate(roles)}


def reasoning_chat(
    db: Session,
    principal: Principal,
    *,
    message: str,
    provider_ids: List[str],
    session_id: Optional[uuid.UUID] = None,
    thinking_mode: str = "balance",
    images: Optional[List[str]] = None,
    section_key: Optional[str] = "general",
) -> dict:
    from app.services import ai_context_builder, memory_extraction_service

    ids = _dedup(provider_ids)
    if not ids:
        raise ValidationAppError("Select at least one AI agent.")
    if len(ids) > MAX_AGENTS_PER_RUN:
        raise ValidationAppError(f"Maximum {MAX_AGENTS_PER_RUN} agents per run.")
    # Thinking Mode drives both reasoning depth and sampling.
    mode = reasoning_depth(thinking_mode)

    # Session + user message.
    if session_id is not None:
        session = db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.workspace_id == principal.workspace_id,
            )
        )
        if not session:
            raise NotFoundError("Chat session not found.")
    else:
        session = ChatSession(workspace_id=principal.workspace_id, created_by=principal.user_id,
                              title=_auto_title(message), section_key=section_key or "general")
        db.add(session)
        db.flush()
    if not (session.title or "").strip():
        session.title = _auto_title(message)
    session.section_key = section_key or "general"

    user_message = ChatMessage(workspace_id=principal.workspace_id, session_id=session.id,
                               role="user", content=message, section_key=section_key or "general",
                               meta=_user_meta("reasoning", thinking_mode, images, section_key or "general"))
    db.add(user_message)
    db.flush()

    run = AiMultiAgentRun(
        workspace_id=principal.workspace_id, session_id=session.id, user_message_id=user_message.id,
        provider_ids=ids, status="running", created_by=principal.user_id,
    )
    db.add(run)
    db.flush()

    plans = {pid: ai_provider_router.plan_chat(db, principal, pid) for pid in ids}
    runnable = {pid: p for pid, p in plans.items() if p.runnable}
    # With an image attached, only vision-capable agents can reason over it.
    has_images = bool(images)
    if has_images:
        runnable = {pid: p for pid, p in runnable.items() if p.supports_image}
    responses: List[AiAgentResponse] = []
    context_meta = {"section_key": section_key or "general", "thinking_mode": thinking_mode}

    def _record(provider_id, provider_name, status, content, error, latency, external, *, phase, extra=None):
        meta = {"external": external, "phase": phase, "reasoning": True}
        meta.update(context_meta)
        if extra:
            meta.update(extra)
        row = AiAgentResponse(
            workspace_id=principal.workspace_id, run_id=run.id, provider_id=provider_id,
            provider_name=provider_name, status=status, content=content, error_message=error,
            latency_ms=latency, meta=meta,
        )
        db.add(row)
        responses.append(row)
        msg_meta = {
            "provider_id": provider_id, "provider_name": provider_name, "status": status,
            "run_id": str(run.id), "latency_ms": latency, "external": external,
            "reasoning": True, "phase": phase,
            **context_meta,
        }
        if extra:
            msg_meta.update(extra)
        db.add(ChatMessage(
            workspace_id=principal.workspace_id, session_id=session.id, role="assistant",
            content=content if status == "completed" and content else (error or status),
            section_key=section_key or "general", meta=msg_meta,
        ))

    # Honest record for agents that can't run.
    for pid in ids:
        if pid in runnable:
            continue
        plan = plans[pid]
        if has_images and plan.runnable and not plan.supports_image:
            status, msg = "unsupported", UNSUPPORTED_IMAGE_MSG
        else:
            status = plan.status if plan.status in ("blocked", "not_configured", "disabled") else "error"
            msg = plan.message
        _record(pid, plan.provider_name, status, None, msg, None, plan.external, phase="analyst")

    task_type = q.detect_task_type(message)
    facts = q.extract_facts(message)
    gen_params = params_for(task_type, mode)
    gen_params.update(thinking_params(thinking_mode))

    if not runnable:
        run.status = "error"
        db.add(ChatMessage(
            workspace_id=principal.workspace_id, session_id=session.id, role="assistant",
            content=("No selected agent could run, so reasoning could not start. Configure and enable "
                     "at least one AI agent in Settings -> AI Providers."),
            section_key=section_key or "general",
            meta={"provider_name": "Reasoning", "status": "error", "run_id": str(run.id),
                  "reasoning": True, "reasoning_final": True, "mode": mode, "task_type": task_type, **context_meta},
        ))
        db.commit()
        db.refresh(run)
        for r in responses:
            db.refresh(r)
        memory_extraction_service.extract_and_commit(
            db, principal, user_msg=message, assistant_msg="", session_id=session.id
        )
        return {"run": run, "session_id": session.id, "responses": responses}

    roles = roles_for(mode)
    runnable_ids = [pid for pid in ids if pid in runnable]
    role_provider = _assign_roles(roles, runnable_ids)

    # Build context packet only after confirming runnable agents exist, so
    # memory mark_used side effects are not triggered on dead-end paths.
    context_packet = ai_context_builder.build(
        db, principal, message=message, session_id=session.id,
        section_key=section_key or "general", thinking_mode=thinking_mode,
    )
    context_meta = context_packet.get("meta", context_meta)
    extra_context = context_packet.get("context")

    # 1) Analyst.
    analyst_pid = role_provider["analyst"]
    analyst_oc = _call(plans[analyst_pid], prompts.analyst_message(message, facts, task_type, extra_context), gen_params, images)
    analyst_answer = analyst_oc["content"] or ""
    _record(analyst_pid, plans[analyst_pid].provider_name, analyst_oc["status"], analyst_oc["content"],
            analyst_oc["error"], analyst_oc["latency_ms"], plans[analyst_pid].external, phase="analyst")

    # 2) Critic (Deep). Its critique relevance is judged so we can reject bad critique.
    critic_answer: Optional[str] = None
    rejected_critique = False
    if "critic" in roles and analyst_answer:
        critic_pid = role_provider["critic"]
        critic_oc = _call(plans[critic_pid], prompts.critic_message(message, analyst_answer), gen_params)
        critic_answer = critic_oc["content"]
        verdict = q.assess_critique(critic_answer or "", message, analyst_answer) if critic_answer else {"relevant": True, "reasons": []}
        rejected_critique = bool(critic_answer) and not verdict["relevant"]
        _record(critic_pid, plans[critic_pid].provider_name, critic_oc["status"], critic_oc["content"],
                critic_oc["error"], critic_oc["latency_ms"], plans[critic_pid].external,
                phase="critic", extra={"critique_relevant": verdict.get("relevant", True),
                                       "critique_reasons": verdict.get("reasons", [])})

    # Concrete issues the verifier found in the analyst answer (authoritative for synthesis).
    issues = q.score_response(message, analyst_answer).issues
    effective_critic = None if rejected_critique else critic_answer

    # 3) Synthesizer (Balanced/Deep) or Analyst-as-final (Fast).
    if "synthesizer" in roles and analyst_answer:
        synth_pid = role_provider["synthesizer"]
        synth_prompt = prompts.synthesizer_message(message, analyst_answer, effective_critic, issues)
        final_oc = _call(plans[synth_pid], synth_prompt, gen_params)
    else:
        synth_pid = analyst_pid
        synth_prompt = None
        final_oc = analyst_oc

    final_answer = final_oc["content"] or ""
    score = q.score_response(message, final_answer)

    # Retry once with stricter grounding if the answer is low quality.
    retried = False
    if final_answer and final_oc["status"] == "completed" and score.is_low() and synth_prompt is not None:
        retried = True
        strict_oc = _call(plans[synth_pid], synth_prompt + prompts.retry_suffix(score.issues),
                          params_for(task_type, "deep"))
        if strict_oc["status"] == "completed" and strict_oc["content"]:
            new_score = q.score_response(message, strict_oc["content"])
            if new_score.final_answer_confidence >= score.final_answer_confidence:
                final_oc, final_answer, score = strict_oc, strict_oc["content"], new_score

    summary = q.reasoning_summary(message, final_answer, score, task_type) if final_oc["status"] == "completed" else ""

    synth_name = plans[synth_pid].provider_name
    final_extra = {
        "reasoning_final": True, "mode": mode, "task_type": task_type, "retried": retried,
        "rejected_critique": rejected_critique, "reasoning_summary": summary,
        "quality": score.to_meta(),
    }
    synth_row = AiAgentResponse(
        workspace_id=principal.workspace_id, run_id=run.id, provider_id=synth_pid,
        provider_name=synth_name, status=final_oc["status"], content=final_oc["content"],
        error_message=final_oc["error"], latency_ms=final_oc["latency_ms"],
        meta={"external": plans[synth_pid].external, "phase": "synthesis", **context_meta, **final_extra},
    )
    db.add(synth_row)
    responses.append(synth_row)
    db.add(ChatMessage(
        workspace_id=principal.workspace_id, session_id=session.id, role="assistant",
        content=final_answer if final_oc["status"] == "completed" and final_answer else (final_oc["error"] or final_oc["status"]),
        section_key=section_key or "general",
        meta={"provider_id": synth_pid, "provider_name": synth_name, "status": final_oc["status"],
              "run_id": str(run.id), "latency_ms": final_oc["latency_ms"],
              "external": plans[synth_pid].external, "reasoning": True, **context_meta, **final_extra},
    ))

    if final_oc["status"] != "completed":
        run.status = "error"
    elif score.is_low() or score.issues:
        run.status = "partial"
    else:
        run.status = "completed"

    db.flush()
    db.commit()
    db.refresh(run)
    for r in responses:
        db.refresh(r)

    # Trigger hybrid memory extraction using the final answer as the assistant
    # reply (fast mode reuses the analyst output as the final answer).
    memory_extraction_service.extract_and_commit(
        db, principal,
        user_msg=message,
        assistant_msg=final_answer or "",
        session_id=session.id,
    )

    return {"run": run, "session_id": session.id, "responses": responses}
