from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import Article, Digest, DigestArticle, Source, Topic, User
from newsagent.models.base import Base
from newsagent.pipeline.render import render_digest_html


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="AI")
        session.add(topic)
        session.flush()
        session.add(Source(id=1, topic_id=topic.id, name="TechCrunch", url="feed://ok", status="approved"))
        session.add(User(id=1, email="user@example.com"))
        session.commit()
        yield session


def add_article(db: Session, *, url_suffix: str, bullets: list[str] | None = None, minutes: int = 3) -> Article:
    article = Article(
        source_id=1,
        title="Original title",
        url=f"https://example.com/{url_suffix}",
        title_he="כותרת בעברית",
        summary_he="תקציר בעברית",
        bullets_he=bullets if bullets is not None else ["נקודה **חשובה** ראשונה", "נקודה שנייה"],
        reading_time_minutes=minutes,
        interestingness=0.5,
        summary_status="summarized",
        relevance_status="relevant",
    )
    db.add(article)
    db.flush()
    return article


def build_digest(db: Session, articles: list[Article], *, intro: str | None = None, joke: str | None = None) -> Digest:
    digest = Digest(user_id=1, date=date(2026, 7, 20), intro_he=intro, dad_joke_he=joke)
    db.add(digest)
    db.flush()
    for a in articles:
        db.add(DigestArticle(digest_id=digest.id, article_id=a.id))
    db.commit()
    db.refresh(digest)
    return digest


def test_render_includes_hebrew_rtl_and_date(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest)
    assert 'dir="rtl"' in html
    assert "כותרת בעברית" in html
    assert "20 ביולי 2026" in html


def test_bullets_render_with_safe_strong_emphasis(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", bullets=["נקודה **חשובה** כאן"])])
    html = render_digest_html(digest)
    assert "<strong>חשובה</strong>" in html


def test_keyword_emphasis_escapes_injected_html(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", bullets=["<script>alert(1)</script> **מפתח**"])])
    html = render_digest_html(digest)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;" in html and "&gt;" in html
    assert "<strong>מפתח</strong>" in html


def test_embedded_latin_brand_name_wrapped_for_bidi_safety(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", bullets=["OpenAI חושפת מודל חדש"])])
    html = render_digest_html(digest)
    assert "<bdi>OpenAI</bdi>" in html


def test_category_tag_uses_hebrew_label_and_color(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest)
    assert "בינה מלאכותית" in html  # Hebrew label for "AI"
    assert "#4ade80" in html  # AI green (WCAG AA against #0b1020)


def test_total_reading_time_sums_displayed_articles(db: Session):
    articles = [add_article(db, url_suffix=str(i), minutes=2) for i in range(3)]
    digest = build_digest(db, articles)
    html = render_digest_html(digest)
    assert "6 דקות קריאה" in html  # 3 articles x 2 min


def test_display_capped_at_five_articles(db: Session):
    articles = [add_article(db, url_suffix=str(i), minutes=1) for i in range(8)]
    digest = build_digest(db, articles)
    html = render_digest_html(digest)
    # Only 5 shown → total reading time capped at 5, not 8
    assert "5 דקות קריאה" in html


def test_tracking_pixel_and_preferences_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest)
    assert f"/t/{digest.tracking_token}.gif" in html
    assert "/preferences" in html


def test_personal_intro_rendered_when_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")], intro="בוקר טוב, נעם!")
    html = render_digest_html(digest)
    assert "בוקר טוב, נעם!" in html


def test_dad_joke_corner_rendered_when_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")], joke="בדיחה מצחיקה כאן")
    html = render_digest_html(digest)
    assert "בדיחה מצחיקה כאן" in html
    assert "קינוח" in html  # corner title


def test_no_joke_corner_when_absent(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest)
    assert "קינוח" not in html


def test_selection_is_topic_diverse(db: Session):
    # 6 AI + 1 Space; diverse round-robin must surface Space within the top 5.
    space_topic = Topic(name="Space")
    db.add(space_topic)
    db.flush()
    db.add(Source(id=2, topic_id=space_topic.id, name="NASA", url="feed://sp", status="approved"))
    db.flush()
    ai = [add_article(db, url_suffix=f"ai{i}") for i in range(6)]
    space = Article(
        source_id=2, title="Space story", url="https://example.com/space",
        title_he="כותרת חלל", bullets_he=["נקודת חלל"], reading_time_minutes=2,
        interestingness=0.5, summary_status="summarized", relevance_status="relevant",
    )
    db.add(space)
    db.flush()
    digest = build_digest(db, ai + [space])
    html = render_digest_html(digest)
    assert "חלל" in html  # the lone Space article is not crowded out
