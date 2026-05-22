"""Multi-agent AI chat: fan one user message out to up to 10 agents at once.

Design notes / safety:
    * Each selected provider is resolved to an honest ``ChatPlan`` on the request
      thread (all DB access happens here). Only the network call runs in a worker
      thread, so the SQLAlchemy session is never shared across threads.
    * One agent failing (error/timeout/blocked) never fails the others — each
      result is captured independently and persisted.
    * No agent may execute writes; this only routes chat and persists results.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.ai import (
    DEFAULT_AGENT_ROLES,
    MAX_AGENTS_PER_RUN,
    AiAgentResponse,
    AiMultiAgentRun,
    ChatMessage,
    ChatSession,
)
from app.services import ai_local_answers, ai_provider_router
from app.services.ai_provider_router import ChatPlan
from app.services.ai_service import _auto_title
from app.services.thinking import thinking_params

# Hard ceiling per agent network call (seconds). Adapters also set their own
# httpx timeouts; this guards against a single agent hanging the whole run.
AGENT_TIMEOUT_SECONDS = 45.0

# Shown when an image is attached but the selected provider has no vision support.
UNSUPPORTED_IMAGE_MSG = (
    "This model can't read images. Choose a vision-capable model "
    "(e.g. GPT-4o, Claude, Gemini, or an Ollama vision model like llava)."
)

# Shown when a vision-capable PROVIDER rejects an image because the chosen MODEL is
# text-only (the provider's API returns a multimodal/"no image endpoint" error).
MODEL_NO_VISION_MSG = (
    "This model can't read images. Pick a vision model in Settings → AI Providers — "
    "e.g. an Ollama vision model (llava, llama3.2-vision), an OpenRouter vision model "
    "(openai/gpt-4o-mini, google/gemini-2.0-flash-001), or the GPT / Claude / Gemini agents."
)
_IMAGE_UNSUPPORTED_HINTS = ("multimodal", "support image", "image input")


def _is_image_unsupported(error: str) -> bool:
    """True if a provider error indicates the model can't accept image input."""
    e = (error or "").lower()
    return any(h in e for h in _IMAGE_UNSUPPORTED_HINTS)


def _dedup(provider_ids: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for pid in provider_ids:
        if pid and pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered


def _user_meta(chat_mode: str, thinking_mode: str, images: Optional[List[str]], section_key: str = "general") -> dict:
    """Metadata persisted on the user's turn: chat mode, thinking mode, section, attachments."""
    meta: dict = {"chat_mode": chat_mode, "thinking_mode": thinking_mode, "section_key": section_key or "general"}
    if images:
        meta["images"] = images
    return meta


def _run_one(plan: ChatPlan, messages: list[dict], params: Optional[dict] = None, has_images: bool = False) -> dict:
    """Execute a single runnable plan and capture an isolated result."""
    started = time.monotonic()
    try:
        result = plan.execute(messages, params)
        latency = int((time.monotonic() - started) * 1000)
        if result.ok:
            return {"status": "completed", "content": result.content, "error": None, "latency_ms": latency}
        # A vision-capable PROVIDER can still reject an image if the chosen MODEL is
        # text-only (e.g. Ollama llama3.1, OpenRouter llama-3.1-8b). Surface that as
        # an honest 'unsupported' with guidance instead of a raw API error.
        if has_images and _is_image_unsupported(result.error or ""):
            return {"status": "unsupported", "content": None, "error": MODEL_NO_VISION_MSG, "latency_ms": latency}
        return {"status": "error", "content": None, "error": result.error, "latency_ms": latency}
    except Exception as exc:  # noqa: BLE001 - one agent's failure stays isolated
        latency = int((time.monotonic() - started) * 1000)
        return {"status": "error", "content": None, "error": str(exc)[:300], "latency_ms": latency}


def multi_chat(
    db: Session,
    principal: Principal,
    *,
    message: str,
    provider_ids: List[str],
    session_id: Optional[uuid.UUID] = None,
    images: Optional[List[str]] = None,
    thinking_mode: str = "balance",
    section_key: Optional[str] = "general",
    response_language: Optional[str] = None,
) -> dict:
    from app.services import ai_context_builder, ai_orchestrator, memory_extraction_service

    ids = _dedup(provider_ids)
    if not ids:
        raise ValidationAppError("Select at least one AI agent.")
    if len(ids) > MAX_AGENTS_PER_RUN:
        raise ValidationAppError(f"Maximum {MAX_AGENTS_PER_RUN} agents per run.")

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
            section_key=section_key or "general",
        )
        db.add(session)
        db.flush()
    # Auto-title an untitled conversation from its first user message.
    if not (session.title or "").strip():
        session.title = _auto_title(message)
    session.section_key = section_key or "general"

    user_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="user",
        content=message,
        section_key=section_key or "general",
        meta=_user_meta("parallel", thinking_mode, images, section_key or "general"),
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

    local = ai_local_answers.direct_answer(message, response_language)
    if local:
        row = AiAgentResponse(
            workspace_id=principal.workspace_id,
            run_id=run.id,
            provider_id="local_clock",
            provider_name="Local Clock",
            status="completed",
            content=local["content"],
            error_message=None,
            latency_ms=0,
            meta={"external": False, "role": "Local", "n_agents": 1},
        )
        db.add(row)
        db.add(ChatMessage(
            workspace_id=principal.workspace_id,
            session_id=session.id,
            role="assistant",
            content=local["content"],
            section_key=section_key or "general",
            meta={
                "provider_id": "local_clock",
                "provider_name": "Local Clock",
                "status": "completed",
                "run_id": str(run.id),
                "latency_ms": 0,
                "external": False,
                "multi": True,
                "role": "Local",
                "n_agents": 1,
                "section_key": section_key or "general",
                "thinking_mode": thinking_mode,
                "tool_calls": [{"tool": local["tool"], "status": "executed", "summary": "done"}],
            },
        ))
        run.status = "completed"
        db.flush()
        db.commit()
        db.refresh(run)
        db.refresh(row)
        memory_extraction_service.extract_and_commit(
            db, principal,
            user_msg=message,
            assistant_msg=local["content"],
            session_id=session.id,
        )
        return {"run": run, "session_id": session.id, "responses": [row]}

    # Resolve every provider on this thread (DB reads only). Ids may be agent
    # refs like "anthropic#2" selecting a provider's secondary model slot.
    plans = {pid: ai_provider_router.plan_chat(db, principal, pid) for pid in ids}
    # Each of the (up to 7) agents gets a distinct role: the slot's configured
    # role when set, otherwise the default for its selection position.
    roles: dict[str, tuple[str, str]] = {}
    for index, pid in enumerate(ids):
        default_name, default_task = DEFAULT_AGENT_ROLES[index % len(DEFAULT_AGENT_ROLES)]
        plan_role = (plans[pid].slot_role or "").strip()
        roles[pid] = (plan_role or default_name, default_task)
    params = thinking_params(thinking_mode)
    has_images = bool(images)

    # Execute only runnable plans; when an image is attached, skip non-vision
    # providers — they are reported as 'unsupported' below instead of running.
    runnable = {pid: p for pid, p in plans.items() if p.runnable and not (has_images and not p.supports_image)}

    # Build memory context only when at least one agent will actually run:
    # build() marks memories as used, and that side effect must not fire when
    # no model sees the context.
    context_packet = (
        ai_context_builder.build(
            db, principal, message=message, session_id=session.id,
            section_key=section_key or "general", thinking_mode=thinking_mode,
            response_language=response_language,
        )
        if runnable
        else {"context": None, "meta": {"section_key": section_key or "general", "thinking_mode": thinking_mode}}
    )
    extra_context = context_packet.get("context")
    context_meta = context_packet.get("meta", {})
    base_user = {"role": "user", "content": message, "images": images or []}

    def _messages_for(pid: str) -> list[dict]:
        role_name, role_task = roles[pid]
        mem_prefix = f"{extra_context}\n\n" if extra_context else ""
        if len(ids) == 1:
            # Single agent: no role framing, but still inject memory context via system msg.
            if mem_prefix:
                return [{"role": "system", "content": mem_prefix.rstrip("\n")}, base_user]
            return [base_user]
        return [
            {"role": "system", "content": (
                f"{mem_prefix}"
                f"You are the {role_name} agent in a team of {len(ids)} AI agents answering "
                f"the same request. Your job: {role_task} Answer from that perspective — "
                "start with the answer, be specific and concrete, no basa-basi, no generic filler, "
                "and be honest about uncertainty. Keep routine replies short. Match the user's "
                "tone: casual chat may be warm/playful, coding gets senior engineering help, and "
                "schedule requests should stay practical."
            )},
            base_user,
        ]

    outcomes: dict[str, dict] = {}
    # 3.9: a money message ALWAYS becomes ONE deterministic finance proposal, regardless
    # of agent count or images — route it through the orchestrator (whose intent router
    # owns finance) instead of fanning out to N free-form agents (which would mis-route to
    # memory/"completed" and could create duplicate proposals).
    from app.services import ai_intent_router, schedule_parser

    is_finance = ai_intent_router.classify(message).is_finance
    # A schedule request must also become ONE deterministic proposal (not N free-form
    # agents echoing "completed"), so routine planning works in multi-agent mode too.
    is_schedule = schedule_parser.parse_schedule(message) is not None
    if runnable and (is_finance or is_schedule or (len(ids) == 1 and not has_images)):
        # The main UI's one-agent Parallel mode should behave like real AI Chat:
        # history + context + safe tool loop + pending actions.
        pid = next(iter(runnable.keys()))
        orchestrated = ai_orchestrator.run_with_tools(
            db, principal, message=message, session_id=session.id, provider_id=pid,
            extra_context=extra_context, section_key=section_key or "general",
            thinking_mode=thinking_mode, user_message_id=user_message.id,
            response_language=response_language,
        )
        outcomes[pid] = {
            "status": "completed" if orchestrated.get("ok") else "error",
            "content": orchestrated.get("content"),
            "error": orchestrated.get("error") or None,
            "latency_ms": None,
            "tool_calls": orchestrated.get("tool_calls") or [],
            "proposal_ids": orchestrated.get("proposal_ids") or [],
        }
    elif runnable:
        with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
            futures = {pool.submit(_run_one, p, _messages_for(pid), params, has_images): pid
                       for pid, p in runnable.items()}
            for future, pid in list(futures.items()):
                try:
                    outcomes[pid] = future.result(timeout=AGENT_TIMEOUT_SECONDS)
                except FutureTimeout:
                    outcomes[pid] = {
                        "status": "error", "content": None,
                        "error": "the agent timed out", "latency_ms": int(AGENT_TIMEOUT_SECONDS * 1000),
                    }

    # Persist one response row per agent (preserving selection order).
    responses: list[AiAgentResponse] = []
    completed = 0
    for pid in ids:
        plan = plans[pid]
        tool_calls: list[dict] = []
        proposal_ids: list[str] = []
        if pid in outcomes:
            oc = outcomes[pid]
            status, content, error, latency = oc["status"], oc["content"], oc["error"], oc["latency_ms"]
            tool_calls = oc.get("tool_calls") or []
            proposal_ids = oc.get("proposal_ids") or []
            if status == "completed":
                completed += 1
        elif has_images and plan.runnable and not plan.supports_image:
            # Configured + enabled, but can't read the attached image.
            status, content, error, latency = "unsupported", None, UNSUPPORTED_IMAGE_MSG, None
        else:
            # Not runnable: honest status straight from the plan.
            status = plan.status if plan.status in ("blocked", "not_configured", "disabled") else "error"
            content, error, latency = None, plan.message, None
        row = AiAgentResponse(
            workspace_id=principal.workspace_id,
            run_id=run.id,
            provider_id=pid,
            provider_name=plan.provider_name,
            status=status,
            content=content,
            error_message=error,
            latency_ms=latency,
            meta={"external": plan.external, "role": roles[pid][0], "n_agents": len(ids)},
        )
        db.add(row)
        responses.append(row)
        # Also persist the agent reply as an assistant ChatMessage so reloading the
        # conversation shows the full thread (content for success, message for errors).
        db.add(
            ChatMessage(
                workspace_id=principal.workspace_id,
                session_id=session.id,
                role="assistant",
                content=content if status == "completed" and content else (error or status),
                section_key=section_key or "general",
                meta={
                    "provider_id": pid,
                    "provider_name": plan.provider_name,
                    "status": status,
                    "run_id": str(run.id),
                    "latency_ms": latency,
                    "external": plan.external,
                    "multi": True,
                    "role": roles[pid][0],
                    "n_agents": len(ids),
                    **context_meta,
                    **({"tool_calls": tool_calls} if tool_calls else {}),
                    **({"proposal_ids": proposal_ids} if proposal_ids else {}),
                },
            )
        )

    if completed == len(ids):
        run.status = "completed"
    elif completed == 0:
        run.status = "error"
    else:
        run.status = "partial"

    db.flush()
    db.commit()
    db.refresh(run)
    for r in responses:
        db.refresh(r)

    # Trigger memory extraction using the user message + first completed agent response.
    first_response = next(
        (r.content for r in responses if r.status == "completed" and r.content),
        "",
    )
    memory_extraction_service.extract_and_commit(
        db, principal,
        user_msg=message,
        assistant_msg=first_response,
        session_id=session.id,
    )

    return {"run": run, "session_id": session.id, "responses": responses}


def get_run(db: Session, principal: Principal, run_id: uuid.UUID) -> dict:
    run = db.scalar(
        select(AiMultiAgentRun).where(
            AiMultiAgentRun.id == run_id,
            AiMultiAgentRun.workspace_id == principal.workspace_id,
        )
    )
    if not run:
        raise NotFoundError("Multi-agent run not found.")
    responses = list(
        db.scalars(
            select(AiAgentResponse)
            .where(
                AiAgentResponse.run_id == run_id,
                AiAgentResponse.workspace_id == principal.workspace_id,
            )
            .order_by(AiAgentResponse.created_at.asc())
        ).all()
    )
    return {"run": run, "session_id": run.session_id, "responses": responses}
