from tests.conftest import API


def test_register_returns_token_and_profile(client):
    response = client.post(
        f"{API}/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "bobPass1234"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "bob"
    assert body["user"]["is_admin"] is False
    assert "password" not in response.text


def test_admin_email_grants_admin_rights(client, admin_headers):
    response = client.get(f"{API}/auth/me", headers=admin_headers)
    assert response.json()["is_admin"] is True


def test_duplicate_email_is_rejected(client, user_headers):
    response = client.post(
        f"{API}/auth/register",
        json={
            "username": "someone-else",
            "email": "alice@example.com",
            "password": "otherPass123",
        },
    )
    assert response.status_code == 409


def test_email_comparison_is_case_insensitive(client, user_headers):
    response = client.post(
        f"{API}/auth/register",
        json={
            "username": "alice-upper",
            "email": "ALICE@example.com",
            "password": "otherPass123",
        },
    )
    assert response.status_code == 409


def test_weak_passwords_are_rejected(client):
    for password in ("short", "12345678", "onlyletters"):
        response = client.post(
            f"{API}/auth/register",
            json={
                "username": "weak",
                "email": "weak@example.com",
                "password": password,
            },
        )
        assert response.status_code == 422, password


def test_login_failure_does_not_distinguish_unknown_user(client, user_headers):
    unknown = client.post(
        f"{API}/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )
    wrong_password = client.post(
        f"{API}/auth/login",
        json={"email": "alice@example.com", "password": "whatever123"},
    )
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json()["detail"] == wrong_password.json()["detail"]


def test_protected_route_requires_a_token(client):
    assert client.get(f"{API}/auth/me").status_code == 401
    assert (
        client.get(
            f"{API}/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        ).status_code
        == 401
    )
