"""Covers cli.py's `usage-report` command - the grouping/filtering logic
over `outbound_calls` had zero test coverage before (round 2 review finding).

`configure_logging()` is monkeypatched to a no-op: usage-report never emits a
log record itself, and calling the real one would mutate the process-wide
root logger (see test_logging_setup.py's own hazard note) for no benefit
here.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from newsagent import cli
from newsagent.models import OutboundCall
from newsagent.models.base import Base


@pytest.fixture
def db_session(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session_local = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(cli, "SessionLocal", test_session_local)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    with test_session_local() as session:
        yield session


def _call(**kwargs) -> OutboundCall:
    defaults: dict = {"purpose": "FILTERING", "target": "llm", "status": "ok"}
    defaults.update(kwargs)
    return OutboundCall(**defaults)


def test_no_calls_prints_the_empty_message(db_session, capsys):
    cli.main(["usage-report"])

    assert "No outbound calls recorded yet." in capsys.readouterr().out


def test_groups_by_purpose_and_sums_tokens(db_session, capsys):
    db_session.add_all(
        [
            _call(purpose="FILTERING", tokens_in=100, tokens_out=10, duration_ms=200),
            _call(purpose="FILTERING", tokens_in=50, tokens_out=5, duration_ms=400),
            _call(purpose="SUMMARIZING", tokens_in=300, tokens_out=80, duration_ms=1000),
        ]
    )
    db_session.commit()

    cli.main(["usage-report"])
    out = capsys.readouterr().out

    assert "FILTERING: 2 calls, 150 in / 15 out tokens, avg 300ms" in out
    assert "SUMMARIZING: 1 calls, 300 in / 80 out tokens, avg 1000ms" in out


def test_avoided_calls_are_excluded_from_the_duration_average(db_session, capsys):
    """Round 2 review finding: a cache hit's near-zero lookup time must not
    drag down the average of the real LLM calls for the same purpose."""
    db_session.add_all(
        [
            _call(purpose="DIGEST_VOICE", status="ok", duration_ms=1000),
            _call(purpose="DIGEST_VOICE", status="avoided", duration_ms=1),
        ]
    )
    db_session.commit()

    cli.main(["usage-report"])
    out = capsys.readouterr().out

    # Both rows count toward the purpose's call total...
    assert "DIGEST_VOICE: 2 calls" in out
    # ...but the average reflects only the real call, not the 1ms cache hit.
    assert "avg 1000ms" in out


def test_purpose_with_only_avoided_calls_has_no_average(db_session, capsys):
    db_session.add_all([_call(purpose="DIGEST_VOICE", status="avoided", duration_ms=1)])
    db_session.commit()

    cli.main(["usage-report"])
    out = capsys.readouterr().out

    assert "DIGEST_VOICE: 1 calls" in out
    assert "avg n/a" in out


def test_waste_counts_retries_avoided_and_malformed(db_session, capsys):
    db_session.add_all(
        [
            _call(purpose="FILTERING", attempt=1, status="error"),
            _call(purpose="FILTERING", attempt=2, status="ok"),
            _call(purpose="DIGEST_VOICE", status="avoided"),
            _call(purpose="SUMMARIZING", status="malformed"),
        ]
    )
    db_session.commit()

    cli.main(["usage-report"])
    out = capsys.readouterr().out

    assert (
        "Waste: 1 retried attempts, 1 avoided (cache-hit) calls, "
        "1 malformed (billed but unusable) calls" in out
    )
