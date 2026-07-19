from fastapi.testclient import TestClient


def test_unauthenticated_gets_401(client: TestClient):
    response = client.get("/admin/sources")
    assert response.status_code == 401


def test_non_admin_user_gets_403(as_user: TestClient):
    response = as_user.get("/admin/sources")
    assert response.status_code == 403


def test_admin_gets_200(as_admin: TestClient):
    response = as_admin.get("/admin/sources")
    assert response.status_code == 200
    assert response.json() == []
