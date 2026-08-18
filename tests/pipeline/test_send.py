from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.mail.base import EmailSendError, EmailSender
from newsagent.models import Article, Digest, DigestArticle, Source, Topic, User
from newsagent.models.base import Base
from newsagent.pipeline.send import send_pending_digests


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="AI")
        session.add(topic)
        session.flush()
        session.add(Source(id=1, topic_id=topic.id, name="Feed", url="feed://ok", status="approved"))
        session.add(User(id=1, email="user@example.com"))
        article = Article(
            source_id=1,
            title="Title",
            url="https://example.com/a",
            title_he="כותרת",
            summary_he="תקציר",
            reading_time_minutes=2,
            summary_status="summarized",
            relevance_status="relevant",
        )
        session.add(article)
        session.flush()
        digest = Digest(id=1, user_id=1, date=date(2026, 7, 20))
        session.add(digest)
        session.flush()
        session.add(DigestArticle(digest_id=digest.id, article_id=article.id))
        session.commit()
        yield session


class RecordingSender(EmailSender):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, html_body: str) -> None:
        self.sent.append((to, subject, html_body))


class FailingSender(EmailSender):
    def send(self, to: str, subject: str, html_body: str) -> None:
        raise EmailSendError("smtp down")


def test_pending_digest_is_sent_and_marked(db: Session):
    sender = RecordingSender()
    report = send_pending_digests(db, sender)
    assert report.sent == 1
    assert len(sender.sent) == 1
    assert sender.sent[0][0] == "user@example.com"
    digest = db.scalar(select(Digest))
    assert digest is not None and digest.sent_at is not None


def test_already_sent_digest_is_not_resent(db: Session):
    sender = RecordingSender()
    send_pending_digests(db, sender)
    report = send_pending_digests(db, sender)
    assert report.sent == 0
    assert len(sender.sent) == 1


def test_failed_send_leaves_sent_at_null_for_retry(db: Session):
    report = send_pending_digests(db, FailingSender())
    assert report.failed == 1
    digest = db.scalar(select(Digest))
    assert digest is not None and digest.sent_at is None


def test_unsubscribed_users_digest_is_not_sent(db: Session):
    """GH #46: catches the same-run race where a user unsubscribes after
    their digest was already built but before send runs."""
    user = db.get(User, 1)
    user.unsubscribed_at = datetime.now()
    db.commit()

    sender = RecordingSender()
    report = send_pending_digests(db, sender)

    assert report.sent == 0
    assert len(sender.sent) == 0
    digest = db.scalar(select(Digest))
    assert digest is not None and digest.sent_at is None
