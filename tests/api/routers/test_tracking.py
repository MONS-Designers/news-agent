from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsagent.api.deps import get_db
from newsagent.api.main import app
from newsagent.config import settings
from newsagent.models import Digest, DigestLink, Feedback, User
from newsagent.models.base import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def digest(db_session: Session) -> Digest:
    db_session.add(User(id=1, email="user@example.com"))
    db_session.flush()
    d = Digest(user_id=1, date=date(2026, 7, 20))
    db_session.add(d)
    db_session.commit()
    return d


def test_valid_token_marks_opened_and_returns_pixel(
    client: TestClient, db_session: Session, digest: Digest
) -> None:
    resp = client.get(f"/t/{digest.tracking_token}.gif")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/gif"
    db_session.refresh(digest)
    assert digest.opened_at is not None


def test_open_records_device_type_from_user_agent(
    client: TestClient, db_session: Session, digest: Digest
) -> None:
    client.get(
        f"/t/{digest.tracking_token}.gif",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
    )
    db_session.refresh(digest)
    assert digest.opened_device_type == "desktop"


def test_open_without_user_agent_records_unknown_device_type(
    client: TestClient, db_session: Session, digest: Digest
) -> None:
    client.get(f"/t/{digest.tracking_token}.gif")
    db_session.refresh(digest)
    assert digest.opened_device_type == "unknown"


def test_second_hit_does_not_overwrite_first_open_time(
    client: TestClient, db_session: Session, digest: Digest
) -> None:
    client.get(f"/t/{digest.tracking_token}.gif")
    db_session.refresh(digest)
    first = digest.opened_at
    client.get(f"/t/{digest.tracking_token}.gif")
    db_session.refresh(digest)
    assert digest.opened_at == first


def test_unknown_token_still_returns_pixel_without_error(client: TestClient) -> None:
    resp = client.get("/t/not-a-real-token.gif")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/gif"


@pytest.fixture
def article_link(db_session: Session, digest: Digest) -> DigestLink:
    link = DigestLink(
        digest_id=digest.id, kind="article", target_url="https://example.com/story"
    )
    db_session.add(link)
    db_session.commit()
    return link


def test_click_redirects_to_real_destination_and_records_click(
    client: TestClient, db_session: Session, article_link: DigestLink
) -> None:
    resp = client.get(f"/c/{article_link.token}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "https://example.com/story"
    db_session.refresh(article_link)
    assert article_link.clicked_at is not None


def test_click_records_device_type_from_user_agent(
    client: TestClient, db_session: Session, article_link: DigestLink
) -> None:
    client.get(
        f"/c/{article_link.token}",
        follow_redirects=False,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "Mobile/15E148 Safari/604.1"
            )
        },
    )
    db_session.refresh(article_link)
    assert article_link.device_type == "mobile"


def test_second_click_does_not_overwrite_first_click_time(
    client: TestClient, db_session: Session, article_link: DigestLink
) -> None:
    client.get(f"/c/{article_link.token}", follow_redirects=False)
    db_session.refresh(article_link)
    first = article_link.clicked_at
    client.get(f"/c/{article_link.token}", follow_redirects=False)
    db_session.refresh(article_link)
    assert article_link.clicked_at == first


def test_unknown_click_token_redirects_to_frontend_without_error(client: TestClient) -> None:
    resp = client.get("/c/not-a-real-token", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == settings.frontend_url


@pytest.fixture
def unsubscribe_link(db_session: Session, digest: Digest) -> DigestLink:
    link = DigestLink(
        digest_id=digest.id, kind="unsubscribe", target_url=f"{settings.frontend_url}/preferences"
    )
    db_session.add(link)
    db_session.commit()
    return link


def test_unsubscribe_click_sets_user_unsubscribed_at(
    client: TestClient, db_session: Session, unsubscribe_link: DigestLink
) -> None:
    client.get(f"/c/{unsubscribe_link.token}", follow_redirects=False)
    user = db_session.get(User, 1)
    assert user is not None
    assert user.unsubscribed_at is not None


def test_unsubscribe_click_twice_does_not_error(
    client: TestClient, db_session: Session, unsubscribe_link: DigestLink
) -> None:
    client.get(f"/c/{unsubscribe_link.token}", follow_redirects=False)
    user = db_session.get(User, 1)
    first = user.unsubscribed_at
    client.get(f"/c/{unsubscribe_link.token}", follow_redirects=False)
    db_session.refresh(user)
    assert user.unsubscribed_at == first


def test_click_marks_digest_as_opened_when_pixel_never_loaded(
    client: TestClient, db_session: Session, digest: Digest, article_link: DigestLink
) -> None:
    assert digest.opened_at is None
    client.get(f"/c/{article_link.token}", follow_redirects=False)
    db_session.refresh(digest)
    assert digest.opened_at is not None


def test_click_does_not_overwrite_earlier_open_time(
    client: TestClient, db_session: Session, digest: Digest, article_link: DigestLink
) -> None:
    client.get(f"/t/{digest.tracking_token}.gif")
    db_session.refresh(digest)
    first = digest.opened_at
    client.get(f"/c/{article_link.token}", follow_redirects=False)
    db_session.refresh(digest)
    assert digest.opened_at == first


def test_article_click_does_not_unsubscribe(
    client: TestClient, db_session: Session, article_link: DigestLink
) -> None:
    client.get(f"/c/{article_link.token}", follow_redirects=False)
    user = db_session.get(User, 1)
    assert user is not None
    assert user.unsubscribed_at is None


@pytest.fixture
def feedback_up_link(db_session: Session, digest: Digest) -> DigestLink:
    link = DigestLink(
        digest_id=digest.id,
        kind="feedback_up",
        target_url=f"{settings.frontend_url}/?feedback=thanks",
    )
    db_session.add(link)
    db_session.commit()
    return link


def test_feedback_click_returns_thanks_page_without_redirect(
    client: TestClient, feedback_up_link: DigestLink
) -> None:
    # No session cookie/header is sent - this is the "reader isn't logged in
    # on this device" case, and the page must render regardless (previously
    # the confirmation lived behind `v-if="me"` in the frontend SPA).
    resp = client.get(f"/c/{feedback_up_link.token}", follow_redirects=False)
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "תודה" in resp.text


def test_feedback_click_records_sentiment(
    client: TestClient, db_session: Session, feedback_up_link: DigestLink
) -> None:
    client.get(f"/c/{feedback_up_link.token}", follow_redirects=False)
    row = db_session.query(Feedback).one()
    assert row.sentiment == "up"
    assert row.digest_id == feedback_up_link.digest_id
