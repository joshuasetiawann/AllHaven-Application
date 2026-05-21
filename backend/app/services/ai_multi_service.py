"""Multi-agent AI chat: fan one user message out to up to 3 agents at once.

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
    MAX_AGENTS_PER_RUN,
    AiAgentResponse,
    AiMultiAgentRun,
    ChatMessage,
    ChatSession,
)
from app.services import ai_provider_router
from app.services.ai_provider_router import ChatPlan
from app.services.ai_service import _auto_title

# Hard ceiling per agent network call (seconds). Adapters also set their own
# httpx timeouts; this guards against a single agent hanging the whole run.
AGENT_TIMEOUT_SECONDS = 45.0


def _dedup(provider_ids: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for pid in provider_ids:
        if pid and pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered


def _run_one(plan: ChatPlan, messages: list[dict], params: Optional[dict] = None) -> dict:
    """Execute a single runnable plan and capture an isolated result."""
    started = time.monotonic()
    try:
        result = plan.execute(messages, params)
        latency = int((time.monotonic() - started) * 1000)
        if result.ok:
            return {"status": "completed", "content": result.content, "error": None, "latency_ms": latency}
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
) -> dict:
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
        )
        db.add(session)
        db.flush()
    # Auto-title an untitled conversation from its first user message.
    if not (session.title or "").strip():
        session.title = _auto_title(message)

    user_message = ChatMessage(
        workspace_id=principal.workspace_id,
        session_id=session.id,
        role="user",
        content=message,
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
    messages = [{"role": "user", "content": message}]

    # Execute only the runnable plans concurrently.
    runnable = {pid: p for pid, p in plans.items() if p.runnable}
    outcomes: dict[str, dict] = {}
    if runnable:
        with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
            futures = {pool.submit(_run_one, p, messages): pid for pid, p in runnable.items()}
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
        if pid in outcomes:
            oc = outcomes[pid]
            status, content, error, latency = oc["status"], oc["content"], oc["error"], oc["latency_ms"]
            if status == "completed":
                completed += 1
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
            meta={"external": plan.external},
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
                meta={
                    "provider_id": pid,
                    "provider_name": plan.provider_name,
                    "status": status,
                    "run_id": str(run.id),
                    "latency_ms": latency,
                    "external": plan.external,
                    "multi": True,
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
