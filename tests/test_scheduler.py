from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.llm import MockLLMProvider
from newsagent.mail.base import EmailSender
from newsagent.models import Article, Digest, Source, Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.models.user import FREQUENCY_DAILY, FREQUENCY_WEEKLY
from newsagent.scheduler import tick
from newsagent.services.scheduler_lease import acquire

TODAY = date(2026, 8, 23)


class RecordingSender(EmailSender):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, html_body: str) -> None:
        self.sent.append((to, subject, html_body))


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(id=1, name="בינה מלאכותית")
        session.add(topic)
        session.flush()
        session.add(
            Source(id=1, topic_id=1, name="Feed", url="feed://ok", status="approved")
        )
        for i in range(3):
            session.add(
                Article(
                    source_id=1,
                    title=f"Story {i}",
                    url=f"https://example.com/{i}",
                    title_he=f"כותרת {i}",
                    summary_he="תקציר",
                    paragraphs_he=["פסקה."],
                    reading_time_minutes=2,
                    interestingness=0.5,
                    summary_status="summarized",
                    relevance_status="relevant",
                    relevance_score=0.8,
                )
            )
        session.commit()
        yield session


def _reader(db: Session, user_id: int, **kwargs) -> User:
    user = User(
        id=user_id, email=f"u{user_id}@example.com", field_name="טכנולוגיה", **kwargs
    )
    db.add(user)
    db.flush()
    db.add(UserTopicPreference(user_id=user_id, topic_id=1))
    db.commit()
    return user


def test_tick_delivers_a_brand_new_readers_first_email(db: Session):
    _reader(db, 1)
    sender = RecordingSender()

    report = tick(db, MockLLMProvider(), sender, TODAY)

    assert report.digests_sent == 1
    assert "שמח שהצטרפת." in sender.sent[0][2]


def test_a_second_tick_sends_nothing_more(db: Session):
    """Idempotence is what makes a two-minute loop safe: a tick that follows a
    completed one must be a no-op, not a duplicate email."""
    _reader(db, 1)
    provider, sender = MockLLMProvider(), RecordingSender()
    tick(db, provider, sender, TODAY)

    report = tick(db, provider, sender, TODAY)

    assert report.digests_sent == 0
    assert report.welcomes_sent == 0
    assert len(sender.sent) == 1


def test_reader_with_no_articles_gets_the_welcome_only_email(db: Session):
    """No topic preference means build_digests creates nothing for them - the
    tick must still honour the promise made at signup."""
    db.add(User(id=2, email="quiet@example.com", field_name="חינוך"))
    db.commit()
    sender = RecordingSender()

    report = tick(db, MockLLMProvider(), sender, TODAY)

    assert report.welcomes_sent == 1
    assert sender.sent[0][0] == "quiet@example.com"


def test_tick_does_nothing_for_a_reader_who_is_not_due_yet(db: Session):
    user = _reader(db, 1, welcomed_at=datetime(2026, 8, 20), digest_frequency=FREQUENCY_WEEKLY)
    db.add(Digest(user_id=user.id, date=date(2026, 8, 20), sent_at=datetime(2026, 8, 20)))
    db.commit()
    sender = RecordingSender()

    report = tick(db, MockLLMProvider(), sender, TODAY)

    assert report.digests_sent == 0
    assert sender.sent == []


def test_tick_delivers_to_a_reader_whose_cadence_came_due(db: Session):
    user = _reader(db, 1, welcomed_at=datetime(2026, 8, 22), digest_frequency=FREQUENCY_DAILY)
    db.add(Digest(user_id=user.id, date=date(2026, 8, 22), sent_at=datetime(2026, 8, 22)))
    db.commit()
    sender = RecordingSender()

    report = tick(db, MockLLMProvider(), sender, TODAY)

    assert report.digests_sent == 1
    # Past the welcome, so it is an ordinary digest now.
    assert "שמח שהצטרפת." not in sender.sent[0][2]


def test_unsubscribed_reader_is_left_alone(db: Session):
    _reader(db, 1, unsubscribed_at=datetime(2026, 8, 1))
    sender = RecordingSender()

    report = tick(db, MockLLMProvider(), sender, TODAY)

    assert report.digests_sent == 0
    assert report.welcomes_sent == 0


def test_a_rival_scheduler_cannot_send_the_same_digest(db: Session):
    """The outcome the lease exists for: two loops against one database
    deliver one email between them, not one each."""
    _reader(db, 1)
    provider = MockLLMProvider()
    first, second = RecordingSender(), RecordingSender()

    assert acquire(db, "scheduler-a") is True
    tick(db, provider, first, TODAY)

    # A second instance wakes up while the first still holds the lease.
    assert acquire(db, "scheduler-b") is False

    assert len(first.sent) == 1
    assert second.sent == []
