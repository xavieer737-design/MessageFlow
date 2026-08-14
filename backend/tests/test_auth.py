"""Authentication tests: registration, login, logout, isolation."""

from tests.conftest import register


def test_register_creates_user_and_sets_cookie(client):
    response = client.post(
        "/api/auth/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "passw0rd1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "password_hash" not in body
    assert "mf_access" in response.cookies


def test_register_rejects_duplicate_email(client):
    register(client)
    response = client.post(
        "/api/auth/register",
        json={"name": "Other", "email": "user@example.com", "password": "passw0rd1"},
    )
    assert response.status_code == 409


def test_register_password_validation(client):
    for password in ["short", "onlyletters", "12345678", ""]:
        response = client.post(
            "/api/auth/register",
            json={"name": "X", "email": "x@example.com", "password": password},
        )
        assert response.status_code == 422, password


def test_login_success_and_failure(client):
    register(client)
    ok = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "passw0rd1"},
    )
    assert ok.status_code == 200
    assert "mf_access" in ok.cookies

    bad = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-pass"},
    )
    assert bad.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(client):
    register(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_logout_clears_session(client):
    register(client)
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_refresh_token(client):
    register(client)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_password_change(client):
    register(client)
    ok = client.put(
        "/api/auth/me/password",
        json={"current_password": "passw0rd1", "new_password": "newpassw0rd"},
    )
    assert ok.status_code == 200
    bad = client.put(
        "/api/auth/me/password",
        json={"current_password": "wrong", "new_password": "newpassw0rd"},
    )
    assert bad.status_code == 400


def test_profile_update(client):
    register(client)
    response = client.put("/api/auth/me", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
