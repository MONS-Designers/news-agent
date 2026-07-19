from fastapi.testclient import TestClient


def test_me_unauthenticated_gets_401(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_identity(as_admin: TestClient):
    response = as_admin.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["is_admin"] is True
    assert body["user_id"] is None


def test_login_without_config_returns_503(client: TestClient):
    # No NEWSAGENT_GOOGLE_CLIENT_ID in the test environment — clear error, not a crash.
    response = client.get("/auth/login")
    assert response.status_code == 503


def test_logout_clears_session(client: TestClient):
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "signed_out"}
