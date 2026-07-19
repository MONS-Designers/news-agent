from fastapi.testclient import TestClient


def test_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/preferences")
    assert response.status_code == 401


def test_user_gets_200(as_user: TestClient):
    response = as_user.get("/me/preferences")
    assert response.status_code == 200
    assert response.json() == []
