from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from newsagent.api.auth import Identity, require_identity, require_user
from newsagent.api.main import app
from newsagent.models import User


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def as_admin(client: TestClient) -> TestClient:
    app.dependency_overrides[require_identity] = lambda: Identity(
        email="admin@example.com", is_admin=True, user_id=None
    )
    return client


@pytest.fixture
def as_user(client: TestClient) -> TestClient:
    app.dependency_overrides[require_identity] = lambda: Identity(
        email="user@example.com", is_admin=False, user_id=1
    )
    app.dependency_overrides[require_user] = lambda: User(id=1, email="user@example.com")
    return client
