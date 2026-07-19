"""Domain services for topics and sources, plus the curated default source
list (issue #16). All operations are get-or-create by natural key, so seeding
is idempotent and safe to re-run."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Source, Topic

# Curated starter feeds per topic — all seeded as approved (admin-curated).
DEFAULT_SOURCES: dict[str, list[tuple[str, str]]] = {
    "AI": [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
        ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ],
    "Cybersecurity": [
        ("SecurityWeek", "https://www.securityweek.com/feed/"),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ],
    "Space": [
        ("NASA Breaking News", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
        ("SpaceNews", "https://spacenews.com/feed/"),
    ],
}


def add_topic(db: Session, name: str) -> tuple[Topic, bool]:
    """Get-or-create a Topic by name. Returns (topic, created)."""
    existing = db.scalar(select(Topic).where(Topic.name == name))
    if existing is not None:
        return existing, False
    topic = Topic(name=name)
    db.add(topic)
    db.commit()
    return topic, True


def add_source(
    db: Session, topic: Topic, name: str, url: str, status: str = "pending"
) -> tuple[Source, bool]:
    """Get-or-create a Source by feed URL. Returns (source, created)."""
    existing = db.scalar(select(Source).where(Source.url == url))
    if existing is not None:
        return existing, False
    source = Source(topic_id=topic.id, name=name, url=url, status=status)
    db.add(source)
    db.commit()
    return source, True


@dataclass
class SeedReport:
    topics_created: int = 0
    sources_created: int = 0


def seed_default_sources(db: Session) -> SeedReport:
    """Load DEFAULT_SOURCES as approved sources under their topics."""
    report = SeedReport()
    for topic_name, feeds in DEFAULT_SOURCES.items():
        topic, created = add_topic(db, topic_name)
        report.topics_created += int(created)
        for source_name, url in feeds:
            _, created = add_source(db, topic, source_name, url, status="approved")
            report.sources_created += int(created)
    return report
