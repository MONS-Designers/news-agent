from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from newsagent.models import Article, Digest, DigestArticle, DigestLink, Source, Topic, User
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


def add_article(
    db: Session,
    *,
    url_suffix: str,
    bullets: list[str] | None = None,
    minutes: int = 3,
    image_url: str | None = None,
) -> Article:
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
        image_url=image_url,
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
    html = render_digest_html(digest, db)
    assert 'dir="rtl"' in html
    assert "כותרת בעברית" in html
    assert "20 ביולי 2026" in html


def test_bullets_render_with_safe_strong_emphasis(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", bullets=["נקודה **חשובה** כאן"])])
    html = render_digest_html(digest, db)
    assert "<strong>חשובה</strong>" in html


def test_keyword_emphasis_escapes_injected_html(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", bullets=["<script>alert(1)</script> **מפתח**"])])
    html = render_digest_html(digest, db)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;" in html and "&gt;" in html
    assert "<strong>מפתח</strong>" in html


def test_embedded_latin_brand_name_wrapped_for_bidi_safety(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", bullets=["OpenAI חושפת מודל חדש"])])
    html = render_digest_html(digest, db)
    assert "<bdi>OpenAI</bdi>" in html


def test_category_tag_uses_hebrew_label_and_color(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest, db)
    assert "בינה מלאכותית" in html  # Hebrew label for "AI"
    assert "#4ade80" in html  # AI green (WCAG AA against #0b1020)


def test_total_reading_time_sums_displayed_articles(db: Session):
    articles = [add_article(db, url_suffix=str(i), minutes=2) for i in range(3)]
    digest = build_digest(db, articles)
    html = render_digest_html(digest, db)
    assert "<bdi>6 דקות קריאה</bdi>" in html  # 3 articles x 2 min


def test_render_does_not_recap_or_drop_articles(db: Session):
    # Selection/capping happens at build time (#25) — render must show
    # digest.articles as-is, however many there are, with nothing dropped.
    articles = [add_article(db, url_suffix=str(i), minutes=1) for i in range(8)]
    digest = build_digest(db, articles)
    html = render_digest_html(digest, db)
    assert "<bdi>8 דקות קריאה</bdi>" in html


def test_reading_time_grouped_with_its_hebrew_unit_in_one_bidi_isolate(db: Session):
    """A bare digit isolated on its own (<bdi>1</bdi> דק' קריאה) could drift
    away from its Hebrew unit during bidi resolution and end up positioned
    next to the wrong neighbor — reported live as "1 · TechCrunch דק' קריאה"
    instead of "TechCrunch · 1 דק' קריאה". Grouping the digit and its unit
    into a single isolate keeps them atomic."""
    digest = build_digest(db, [add_article(db, url_suffix="a", minutes=1)])
    html = render_digest_html(digest, db)
    assert "<bdi>1 דק׳ קריאה</bdi>" in html
    source_pos = html.index("<bdi>TechCrunch</bdi>")
    reading_time_pos = html.index("<bdi>1 דק׳ קריאה</bdi>")
    assert source_pos < reading_time_pos


def test_tracking_pixel_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest, db)
    assert f"/t/{digest.tracking_token}.gif" in html


def test_article_link_is_click_tracked_not_raw_url(db: Session):
    article = add_article(db, url_suffix="a")
    digest = build_digest(db, [article])
    html = render_digest_html(digest, db)
    link = db.scalar(select(DigestLink).where(DigestLink.article_id == article.id))
    assert link is not None
    assert link.target_url == article.url
    assert f"/c/{link.token}" in html
    assert article.url not in html


def test_preferences_link_is_click_tracked(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest, db)
    link = db.scalar(
        select(DigestLink).where(DigestLink.digest_id == digest.id, DigestLink.kind == "preferences")
    )
    assert link is not None
    assert link.target_url.endswith("/preferences")
    assert f"/c/{link.token}" in html


def test_unsubscribe_link_is_click_tracked(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest, db)
    link = db.scalar(
        select(DigestLink).where(DigestLink.digest_id == digest.id, DigestLink.kind == "unsubscribe")
    )
    assert link is not None
    assert f"/c/{link.token}" in html


def test_rerender_reuses_same_link_tokens(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    render_digest_html(digest, db)
    first_count = db.scalar(select(func.count()).select_from(DigestLink))
    render_digest_html(digest, db)
    second_count = db.scalar(select(func.count()).select_from(DigestLink))
    assert first_count == second_count


def test_personal_intro_rendered_when_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")], intro="בוקר טוב, נעם!")
    html = render_digest_html(digest, db)
    assert "בוקר טוב, נעם!" in html


def test_dad_joke_corner_rendered_when_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")], joke="בדיחה מצחיקה כאן")
    html = render_digest_html(digest, db)
    assert "בדיחה מצחיקה כאן" in html
    assert "קינוח" in html  # corner title


def test_no_joke_corner_when_absent(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])
    html = render_digest_html(digest, db)
    assert "קינוח" not in html


def test_lead_image_rendered_when_present(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a", image_url="https://img/lead.jpg")])
    html = render_digest_html(digest, db)
    assert 'src="https://img/lead.jpg"' in html
    assert "height:auto" in html  # resilient collapse for blocked images


def test_lead_image_alt_is_plain_title_not_markup(db: Session):
    # alt must be plain text — the <bdi>/<strong> markup that title_he carries
    # cannot live inside an HTML attribute.
    digest = build_digest(db, [add_article(db, url_suffix="a", image_url="https://img/x.jpg")])
    html = render_digest_html(digest, db)
    assert 'alt="כותרת בעברית"' in html


def test_no_image_element_when_absent(db: Session):
    digest = build_digest(db, [add_article(db, url_suffix="a")])  # image_url defaults to None
    html = render_digest_html(digest, db)
    # The lead image carries the title as its alt; the tracking pixel uses alt="".
    # No title-alt image → the article degraded to a text-only card.
    assert 'alt="כותרת בעברית"' not in html
