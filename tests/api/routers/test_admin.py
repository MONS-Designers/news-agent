from fastapi.testclient import TestClient

from newsagent.api.main import app

client = TestClient(app)


def test_admin_sources_stub_responds():
    response = client.get("/admin/sources")
    assert response.status_code == 200
    assert response.json() == []
