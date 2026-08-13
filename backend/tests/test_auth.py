"""Auth flow tests: register, login, me, and error cases."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local

import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.database import make_engine
from app.core.exceptions import ConflictError
from app.domain.base import Base
from app.domain.users import LocalUser, Profile
from app.services import auth_service
from tests.conftest import API


def test_register_creates_user_and_workspace(client):
    resp = client.post(
        f"{API}/auth/register",
        json={"email": "a@example.com", "password": "password123", "full_name": "Alice"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["access_token"]
    assert data["user"]["email"] == "a@example.com"
    assert "hashed_password" not in data["user"]


def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    assert client.post(f"{API}/auth/register", json=payload).status_code == 200
    resp = client.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "EMAIL_TAKEN"


def test_register_normalizes_case_before_duplicate_check(client):
    payload = {"email": "Case.Race@example.com", "password": "password123"}
    assert client.post(f"{API}/auth/register", json=payload).status_code == 200
    payload["email"] = "CASE.RACE@EXAMPLE.COM"
    response = client.post(f"{API}/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error_code"] == "EMAIL_TAKEN"


def test_register_integrity_race_is_translated_without_sql_or_hash(db_session, monkeypatch):
    email = "race@example.com"
    winner = LocalUser(
        id=uuid.uuid4(),
        email=email,
        hashed_password=auth_service.hash_password("winner-password"),
    )
    db_session.add(winner)
    db_session.commit()

    def raced(*_args, **_kwargs):
        raise IntegrityError("INSERT local_users", {"hashed_password": "secret"}, Exception("unique"))

    monkeypatch.setattr(auth_service, "_register_user_unchecked", raced)
    with pytest.raises(Exception) as raised:
        auth_service.register_user(
            db_session,
            email=email.upper(),
            password="loser-password",
            full_name=None,
        )
    assert getattr(raised.value, "status_code", None) == 409
    assert getattr(raised.value, "error_code", None) == "EMAIL_TAKEN"
    assert "secret" not in str(raised.value)


def test_concurrent_case_variant_registrations_yield_one_success_one_409(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'registration-race.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)
    thread_state = local()
    original_lookup = auth_service.get_user_by_email

    def synchronized_lookup(db, email):
        if not getattr(thread_state, "passed_preflight", False):
            thread_state.passed_preflight = True
            barrier.wait(timeout=5)
        return original_lookup(db, email)

    monkeypatch.setattr(auth_service, "get_user_by_email", synchronized_lookup)

    def register(email):
        db = sessions()
        try:
            auth_service.register_user(
                db, email=email, password="password123", full_name="Race"
            )
            return 200, None
        except ConflictError as exc:
            return exc.status_code, exc.error_code
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, ["race.user@example.com", "RACE.USER@EXAMPLE.COM"]))

    assert sorted(results) == [(200, None), (409, "EMAIL_TAKEN")]
    with sessions() as db:
        assert db.query(LocalUser).count() == 1
        assert db.query(Profile).count() == 1
    engine.dispose()


def test_email_over_320_characters_is_rejected(client):
    email = f"{'a' * 309}@example.com"  # 321 characters
    assert len(email) == 321
    for path in ("register", "login"):
        response = client.post(
            f"{API}/auth/{path}",
            json={"email": email, "password": "password123"},
        )
        assert response.status_code == 422


def test_missing_and_inactive_accounts_use_dummy_password_verification(db_session, monkeypatch):
    calls: list[str] = []

    def tracked(_password, stored):
        calls.append(stored)
        return False

    monkeypatch.setattr(auth_service, "verify_password", tracked)
    assert auth_service.authenticate(
        db_session, email="missing@example.com", password="wrong"
    ) is None

    inactive = LocalUser(
        email="inactive@example.com",
        hashed_password="real-user-hash-must-not-be-used",
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()
    assert auth_service.authenticate(
        db_session, email=inactive.email, password="wrong"
    ) is None
    assert calls == [auth_service._DUMMY_PASSWORD_HASH, auth_service._DUMMY_PASSWORD_HASH]


def test_login_success_and_me(client):
    client.post(
        f"{API}/auth/register",
        json={"email": "b@example.com", "password": "password123", "full_name": "Bob"},
    )
    login = client.post(
        f"{API}/auth/login", json={"email": "b@example.com", "password": "password123"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]

    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    me_data = me.json()["data"]
    assert me_data["user"]["email"] == "b@example.com"
    assert me_data["workspace"]["name"] == "Bob's Workspace"


def test_login_wrong_password_is_generic_401(client):
    client.post(f"{API}/auth/register", json={"email": "c@example.com", "password": "password123"})
    resp = client.post(
        f"{API}/auth/login", json={"email": "c@example.com", "password": "wrongpass1"}
    )
    assert resp.status_code == 401
    # Generic message: does not reveal whether email or password was wrong.
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


def test_me_requires_auth(client):
    resp = client.get(f"{API}/auth/me")
    assert resp.status_code == 401


def test_update_profile_and_workspace(auth_client):
    from tests.conftest import API

    resp = auth_client.patch(
        f"{API}/auth/me",
        json={"full_name": "Renamed Operator", "workspace_name": "Acme HQ"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["user"]["full_name"] == "Renamed Operator"
    assert data["workspace"]["name"] == "Acme HQ"
    # Persisted.
    me = auth_client.get(f"{API}/auth/me").json()["data"]
    assert me["user"]["full_name"] == "Renamed Operator"
    assert me["workspace"]["name"] == "Acme HQ"


def test_register_never_adopts_an_existing_profile_by_email(client, db_session):
    """An unauthenticated registration cannot claim a synced victim profile."""
    import uuid

    from app.domain.users import LocalUser, Profile
    from app.domain.workspaces import Workspace, WorkspaceMember

    email = f"synced-{uuid.uuid4().hex[:8]}@example.com"
    synced_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    db_session.add(Profile(id=synced_id, email=email, full_name="Synced User"))
    db_session.add(Workspace(id=ws_id, name="Synced Workspace", owner_id=synced_id))
    db_session.add(WorkspaceMember(workspace_id=ws_id, user_id=synced_id, role="owner"))
    db_session.commit()

    resp = client.post(
        f"{API}/auth/register",
        json={
            "email": email.upper(),
            "password": "attacker-password",
            "full_name": "Attacker",
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error_code"] == "TRUSTED_LINK_REQUIRED"

    assert db_session.query(LocalUser).filter(LocalUser.email == email).count() == 0
    assert db_session.query(Profile).filter(Profile.email == email).count() == 1
    victim = db_session.get(Profile, synced_id)
    workspace = db_session.get(Workspace, ws_id)
    assert victim.full_name == "Synced User"
    assert workspace.name == "Synced Workspace"
    assert workspace.owner_id == synced_id
    membership = db_session.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == ws_id,
        WorkspaceMember.user_id == synced_id,
    ).one()
    assert membership.role == "owner"
