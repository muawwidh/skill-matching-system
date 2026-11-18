from fastapi.testclient import TestClient


def test_register_login_and_read_current_user(client: TestClient) -> None:
    payload = {
        "email": "candidate@example.com",
        "full_name": "Candidate Example",
        "password": "correct-horse-password",
    }

    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201
    tokens = register_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["email"] == payload["email"]
    assert body["roles"] == [{"name": "candidate"}]

    login_response = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    payload = {
        "email": "candidate@example.com",
        "full_name": "Candidate Example",
        "password": "correct-horse-password",
    }

    assert client.post("/auth/register", json=payload).status_code == 201
    duplicate_response = client.post("/auth/register", json=payload)
    assert duplicate_response.status_code == 409


def test_invalid_login_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "bad-password"},
    )
    assert response.status_code == 401


def test_refresh_rotates_tokens_and_rejects_reuse(client: TestClient) -> None:
    # The frontend renews an expired access token through this endpoint on a 401 and retries once.
    payload = {"email": "refresh@example.com", "full_name": "Refresh Example", "password": "correct-horse-password"}
    tokens = client.post("/auth/register", json=payload).json()

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    renewed = refreshed.json()
    assert renewed["refresh_token"] != tokens["refresh_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {renewed['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == payload["email"]

    # Rotation: the old refresh token is revoked, so only one concurrent refresh can succeed.
    reused = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_expired_access_token_is_rejected_with_401(client: TestClient, monkeypatch) -> None:
    from app.core.config import settings
    from app.core.security import create_access_token

    payload = {"email": "expired@example.com", "full_name": "Expired Example", "password": "correct-horse-password"}
    client.post("/auth/register", json=payload)
    me = client.post("/auth/login", json={"email": payload["email"], "password": payload["password"]})
    user_id = client.get("/auth/me", headers={"Authorization": f"Bearer {me.json()['access_token']}"}).json()["id"]
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    expired = create_access_token(user_id, [])
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials."
