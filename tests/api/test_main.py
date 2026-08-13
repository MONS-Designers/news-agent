import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from newsagent.api.main import app, create_app
from newsagent.config import settings

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_configured_frontend_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    test_client = TestClient(create_app())

    response = test_client.get("/health", headers={"Origin": "https://app.example.com"})

    assert response.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_cors_rejects_unconfigured_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    test_client = TestClient(create_app())

    other_origin = "https://not-the-frontend.example.com"
    response = test_client.get("/health", headers={"Origin": other_origin})

    assert "access-control-allow-origin" not in response.headers


def test_session_cookie_domain_applied_when_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    monkeypatch.setattr(settings, "session_cookie_domain", ".example.com")
    test_app = create_app()

    @test_app.get("/__test_session__")
    def _set_session(request: Request) -> dict[str, bool]:
        request.session["x"] = "1"
        return {"ok": True}

    with TestClient(test_app) as test_client:
        response = test_client.get("/__test_session__")

    assert "domain=.example.com" in response.headers.get("set-cookie", "")


def test_session_cookie_has_no_domain_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    monkeypatch.setattr(settings, "session_cookie_domain", "")
    test_app = create_app()

    @test_app.get("/__test_session__")
    def _set_session(request: Request) -> dict[str, bool]:
        request.session["x"] = "1"
        return {"ok": True}

    with TestClient(test_app) as test_client:
        response = test_client.get("/__test_session__")

    assert "domain=" not in response.headers.get("set-cookie", "")
