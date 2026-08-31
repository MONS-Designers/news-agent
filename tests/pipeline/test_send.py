from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.mail.base import EmailSendError, EmailSender
from newsagent.models import Article, Digest, DigestArticle, Source, Topic, User
from newsagent.models.base import Base
from newsagent.pipeline.send import send_pending_digests, send_pending_welcomes


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


# --- One-time beta welcome ------------------------------------------------


def test_first_digest_carries_the_welcome_and_stamps_the_user(db: Session):
    user = db.get(User, 1)
    user.name = "נעם מגנוס"
    user.field_name = "עיצוב"
    db.commit()
    sender = RecordingSender()

    send_pending_digests(db, sender)

    _, subject, html = sender.sent[0]
    assert subject == "נעם, הדייג'סט הראשון שלך מוכן."
    assert "שמח שהצטרפת." in html
    assert "שבחרת בעיצוב" in html
    assert user.welcomed_at is not None


def test_welcome_appears_only_once(db: Session):
    """welcomed_at is what makes the second send an ordinary digest."""
    user = db.get(User, 1)
    user.welcomed_at = datetime(2026, 7, 1)
    db.commit()
    sender = RecordingSender()

    send_pending_digests(db, sender)

    _, subject, html = sender.sent[0]
    assert "שמח שהצטרפת." not in html
    # The sender name already shows "NewsAgent" - the subject leads straight
    # with the headline instead of repeating it.
    assert subject == "כותרת"


def test_failed_first_send_keeps_the_welcome_owed(db: Session):
    """A send that never arrived must not cost the reader their welcome."""
    user = db.get(User, 1)
    db.commit()

    send_pending_digests(db, FailingSender())

    assert user.welcomed_at is None


def test_welcome_without_a_name_omits_the_greeting_line(db: Session):
    user = db.get(User, 1)
    user.field_name = "עיצוב"
    db.commit()
    sender = RecordingSender()

    send_pending_digests(db, sender)

    _, subject, html = sender.sent[0]
    assert subject == "הדייג'סט הראשון שלך מוכן."
    assert "שלום ," not in html
    assert "שמח שהצטרפת." in html


def test_user_with_no_articles_still_gets_a_beta_only_welcome(db: Session):
    """build_digests creates no Digest for them, so the digest path can never
    reach them - finishing setup must not be met with silence."""
    db.add(User(id=2, email="quiet@example.com", name="דנה", field_name="חינוך"))
    db.commit()
    sender = RecordingSender()

    report = send_pending_welcomes(db, sender)

    assert report.sent == 1
    to, subject, html = sender.sent[0]
    assert to == "quiet@example.com"
    assert subject == "דנה, הדייג'סט הראשון שלך מוכן."
    assert "עדיף לי לחכות יום מאשר לשלוח רעש" in html
    assert "👍" not in html  # nothing to rate yet
    assert db.get(User, 2).welcomed_at is not None


def test_welcome_only_skips_users_who_have_a_digest(db: Session):
    """User 1 has a digest, so the digest path owns their welcome - sending
    both would greet the same reader twice."""
    db.commit()

    report = send_pending_welcomes(db, RecordingSender())

    assert report.sent == 0


def test_welcome_only_skips_users_who_never_finished_setup(db: Session):
    db.add(User(id=3, email="browsing@example.com"))
    db.commit()

    report = send_pending_welcomes(db, RecordingSender())

    assert report.sent == 0


def test_no_name_means_no_first_name_greeting_anywhere(db: Session):
    """An address is not a name. With no name stored, both the subject and the
    body must drop the greeting entirely rather than falling back to the email
    or to a placeholder."""
    user = db.get(User, 1)
    user.name = None
    user.field_name = "עיצוב"
    db.commit()
    sender = RecordingSender()

    send_pending_digests(db, sender)

    _, subject, html = sender.sent[0]
    assert subject == "הדייג'סט הראשון שלך מוכן."
    assert "user@example.com" not in html
    assert "שלום" not in html
    assert "שמח שהצטרפת." in html


def test_only_the_first_name_is_used(db: Session):
    user = db.get(User, 1)
    user.name = "דנה לוי-כהן"
    db.commit()
    sender = RecordingSender()

    send_pending_digests(db, sender)

    _, subject, html = sender.sent[0]
    assert subject == "דנה, הדייג'סט הראשון שלך מוכן."
    assert "שלום דנה," in html
