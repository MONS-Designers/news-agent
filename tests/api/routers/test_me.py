from fastapi.testclient import TestClient

from newsagent.api.main import app

client = TestClient(app)


def test_me_preferences_stub_responds():
    response = client.get("/me/preferences")
    assert response.status_code == 200
    assert response.json() == []
