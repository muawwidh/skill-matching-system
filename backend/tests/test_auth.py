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
