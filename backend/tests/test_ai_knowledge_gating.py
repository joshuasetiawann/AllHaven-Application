"""Knowledge is REAL (injected into the model prompt) but must be relevance-gated:
a casual message should not pull in the document inventory, a weak single-token match
should not be injected, and a genuinely relevant question should be.
"""
import uuid

from app.core.principal import Principal
from app.services import ai_context_builder
from tests.conftest import API


def _principal(auth_client) -> Principal:
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    return Principal(
        user_id=uuid.UUID(me["user"]["id"]),
        workspace_id=uuid.UUID(me["workspace"]["id"]),
        email=me["user"]["email"],
    )


def _upload(auth_client, name, body):
    r = auth_client.post(
        f"{API}/ai/knowledge/documents",
        files={"file": (name, body, "text/plain")},
    )
    assert r.status_code == 200, r.text


def test_casual_message_does_not_inject_knowledge(auth_client, db_session):
    _upload(
        auth_client, "vpn.txt",
        b"To configure the office VPN, install WireGuard and import the company tunnel profile.",
    )
    principal = _principal(auth_client)
    res = ai_context_builder.build(
        db_session, principal, message="hai", section_key="general",
    )
    assert res["meta"]["used_knowledge"] is False
    assert "AI Knowledge" not in (res["context"] or "")


def test_relevant_question_injects_knowledge_real(auth_client, db_session):
    _upload(
        auth_client, "vpn.txt",
        b"To configure the office VPN, install WireGuard and import the company tunnel profile.",
    )
    principal = _principal(auth_client)
    res = ai_context_builder.build(
        db_session, principal,
        message="how do I configure the office VPN tunnel with WireGuard?",
        section_key="general",
    )
    assert res["meta"]["used_knowledge"] is True
    assert res["meta"]["knowledge_sources"]
    assert "WireGuard" in (res["context"] or "")


def test_weak_single_token_match_is_gated_out(auth_client, db_session):
    _upload(
        auth_client, "vpn.txt",
        b"To configure the office VPN, install WireGuard and import the company tunnel profile.",
    )
    principal = _principal(auth_client)
    # Shares only the stop-ish token "the" / "to" with the doc — must not be injected.
    res = ai_context_builder.build(
        db_session, principal, message="what is the weather like today outside",
        section_key="general",
    )
    assert res["meta"]["used_knowledge"] is False
