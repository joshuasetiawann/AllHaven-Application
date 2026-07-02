"""Auth flow tests: register, login, me, and error cases."""

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
