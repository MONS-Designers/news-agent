from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import (
    Admin,
    Article,
    Base,
    Digest,
    DigestArticle,
    Field,
    LogEntry,
    PendingTaxonomySuggestion,
    PipelineRun,
    Role,
    Source,
    Topic,
    User,
    UserTopicPreference,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_and_query_one_row_per_table(session: Session):
    admin = Admin(email="admin@example.com")
    topic = Topic(name="AI")
    source = Source(topic=topic, url="https://example.com/feed", name="Example Feed")
    article = Article(source=source, title="An article", url="https://example.com/a1")
    user = User(email="user@example.com", name="Test User")
    preference = UserTopicPreference(user=user, topic=topic)
    digest = Digest(user=user, date=date.today())
    digest_article = DigestArticle(digest=digest, article=article)
    field = Field(name="Tech")
    role = Role(field=field, name="Software Engineer")
    pending_taxonomy_suggestion = PendingTaxonomySuggestion(
        kind="field", field_id=None, normalized_text="tech writer", status="pending"
    )
    pipeline_run = PipelineRun(run_type="filter")
    log_entry = LogEntry(
        level="WARNING", logger_name="newsagent.pipeline.fetcher", message="boom", version="0.1.0"
    )

    session.add_all(
        [
            admin,
            topic,
            source,
            article,
            user,
            preference,
            digest,
            digest_article,
            field,
            role,
            pending_taxonomy_suggestion,
            pipeline_run,
            log_entry,
        ]
    )
    session.commit()

    assert session.query(Admin).count() == 1
    assert session.query(Topic).count() == 1
    assert session.query(Source).count() == 1
    assert session.query(Article).count() == 1
    assert session.query(User).count() == 1
    assert session.query(UserTopicPreference).count() == 1
    assert session.query(Digest).count() == 1
    assert session.query(DigestArticle).count() == 1
    assert session.query(Field).count() == 1
    assert session.query(Role).count() == 1
    assert session.query(PendingTaxonomySuggestion).count() == 1
    assert session.query(PipelineRun).count() == 1
    assert session.query(LogEntry).count() == 1
