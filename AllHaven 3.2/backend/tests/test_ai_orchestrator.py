"""Tests for the orchestrator's extra_context injection (memory context).

Providers are stubbed via ``plan_chat`` (same pattern as test_ai_debate.py) so we
exercise exactly what run_with_tools sends to the provider: extra_context must
land in the system message on tool-capable plans, and be prepended to the user
turn on plans without tool support.
"""

import uuid

import app.services.ai_provider_router as router_mod
from app.core.principal import Principal
from app.services import ai_orchestrator
from app.services.ai_orchestrator import SYSTEM_PROMPT
from app.services.ai_provider_router import ChatPlan
from app.services.ai_providers.base import ChatResult
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _fake_plan(captured: dict, *, tool_loop: bool) -> ChatPlan:
    def _runner(messages, params=None, tools=None):
        captured["messages"] = messages
        return ChatResult(True, content="stub reply")

    return ChatPlan(
        "openai", "GPT Agent", True, True, True, "queued", "", _runner,
        supports_tool_loop=tool_loop,
    )


def _patch_plan(monkeypatch, plan: ChatPlan) -> None:
    monkeypatch.setattr(router_mod, "plan_chat", lambda db, principal, pid=None: plan)


def test_extra_context_lands_in_system_message(auth_client, db_session, monkeypatch):
    captured: dict = {}
    _patch_plan(monkeypatch, _fake_plan(captured, tool_loop=True))
    result = ai_orchestrator.run_with_tools(
        db_session, _principal(auth_client),
        message="What do you know about me?",
        extra_context="## What I know about the user\n- Prefers dark mode",
    )
    assert result["ok"] is True
    system = captured["messages"][0]
    assert system["role"] == "system"
    assert system["content"].startswith(SYSTEM_PROMPT)
    assert "Prefers dark mode" in system["content"]


def test_no_extra_context_keeps_plain_system_prompt(auth_client, db_session, monkeypatch):
    captured: dict = {}
    _patch_plan(monkeypatch, _fake_plan(captured, tool_loop=True))
    result = ai_orchestrator.run_with_tools(
        db_session, _principal(auth_client), message="Hello",
    )
    assert result["ok"] is True
    assert captured["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}


def test_extra_context_prepended_on_non_tool_path(auth_client, db_session, monkeypatch):
    captured: dict = {}
    _patch_plan(monkeypatch, _fake_plan(captured, tool_loop=False))
    result = ai_orchestrator.run_with_tools(
        db_session, _principal(auth_client),
        message="Hello",
        extra_context="## What I know about the user\n- Speaks Indonesian",
    )
    assert result["ok"] is True
    system_turn = captured["messages"][0]
    user_turn = captured["messages"][-1]
    assert system_turn["role"] == "system"
    assert system_turn["content"].startswith(SYSTEM_PROMPT)
    assert "Speaks Indonesian" in system_turn["content"]
    assert user_turn == {"role": "user", "content": "Hello"}
