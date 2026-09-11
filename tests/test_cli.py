"""Covers every subcommand cli.py registers.

The pipeline and service functions behind the commands are tested in their own
modules. What lives only here is the glue: which report field lands in which
slot of the printed line, which arguments reach the service, the exit code an
operator script branches on, and the ordering guarantees the dispatch body
encodes.

`configure_logging()` is monkeypatched to a no-op: calling the real one would
mutate the process-wide root logger (see test_logging_setup.py's own hazard
note), and `basicConfig(force=True)` would drop pytest's caplog handler along
with it.
"""

import logging
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from newsagent import cli, logging_setup
from newsagent.models import OutboundCall
from newsagent.models.base import Base
from newsagent.pipeline.digest import DigestReport
from newsagent.pipeline.extract import ExtractReport
from newsagent.pipeline.fetcher import FetchReport, SourceResult
from newsagent.pipeline.relevance import FilterReport
from newsagent.pipeline.send import SendReport
from newsagent.pipeline.summarize import SummarizeReport
from newsagent.telemetry.pricing import RefreshResult


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


# -- refresh-pricing -----------------------------------------------------
# Exit codes are the entire contract with news-agent-infra's scheduler
# (infra-boundary-contract.md): 0 updated, 2 source unavailable (not a
# failure), 1 a real failure.


def test_refresh_pricing_success_prints_count_and_returns_zero(db_session, monkeypatch, capsys):
    monkeypatch.setattr(cli.pricing_service, "refresh_from_openrouter", lambda db: RefreshResult(updated=3))

    exit_code = cli.main(["refresh-pricing"])

    assert exit_code == 0
    assert "Updated pricing for 3 model(s)" in capsys.readouterr().out


def test_refresh_pricing_source_unavailable_returns_two(db_session, monkeypatch):
    def _raise(db):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(cli.pricing_service, "refresh_from_openrouter", _raise)

    assert cli.main(["refresh-pricing"]) == 2


def test_refresh_pricing_real_failure_returns_one_and_logs_error(db_session, monkeypatch, caplog):
    def _raise(db):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(cli.pricing_service, "refresh_from_openrouter", _raise)

    with caplog.at_level(logging.ERROR, logger="newsagent.cli"):
        exit_code = cli.main(["refresh-pricing"])

    assert exit_code == 1
    assert "refresh-pricing failed" in caplog.text


# --- `filter` / `summarize` command wiring (GH #43) ---------------------------
#
# The pipeline functions themselves are covered in tests/pipeline/. What had no
# coverage is cli.py's glue around them: which report field lands in which slot
# of the printed line, that the provider actually reaches the call, and that
# both the pipeline work and the run-id attach happen *inside* the tracking
# block. Either one drifting out of it silently correlates nothing: the work
# emits its log records before tracking starts, or the attach runs after the
# tracked ids are already gone.


@pytest.fixture
def stub_provider(monkeypatch: pytest.MonkeyPatch) -> object:
    """Stands in for the real provider, which would need real config to build.
    Returned so a test can assert this exact object reached the pipeline."""
    provider = object()
    monkeypatch.setattr(cli, "get_llm_provider", lambda: provider)
    return provider


def _stub_stage(monkeypatch, module: str, attr: str, report: object) -> dict:
    """Replaces one pipeline stage and records what the command handed it,
    including whether log tracking was already active when it was called."""
    seen: dict = {}

    def fake(db, provider):
        seen["provider"] = provider
        seen["tracked"] = logging_setup._tracked_ids.get() is not None
        return report

    monkeypatch.setattr(getattr(cli, module), attr, fake)
    return seen


def _run_filter(monkeypatch, report: FilterReport) -> dict:
    return _stub_stage(monkeypatch, "relevance", "filter_pending_articles", report)


def _run_summarize(monkeypatch, report: SummarizeReport) -> dict:
    return _stub_stage(monkeypatch, "summarize", "summarize_relevant_articles", report)


def _capture_attach(monkeypatch) -> list[tuple[int, bool]]:
    """Records each attach call as (run_id, was the tracking block active)."""
    calls: list[tuple[int, bool]] = []

    def fake(db, run_id: int) -> None:
        calls.append((run_id, logging_setup._tracked_ids.get() is not None))

    monkeypatch.setattr(cli, "attach_outbound_run", fake)
    return calls


def _break_attach(monkeypatch) -> None:
    def boom(db, run_id):
        raise RuntimeError("db gone")

    monkeypatch.setattr(cli, "attach_outbound_run", boom)


def test_filter_prints_every_report_number_in_its_own_slot(
    db_session, stub_provider, monkeypatch, capsys
):
    """Six distinct values, so any transposed pair fails the assert. They are
    also internally consistent: relevance.py appends one score per article it
    scores, so len(scores) always equals relevant + irrelevant, and the two
    scores between the 0.3/0.7 contract anchors are the borderline count."""
    seen = _run_filter(
        monkeypatch,
        FilterReport(
            relevant=3,
            irrelevant=5,
            refused=1,
            errors=4,
            scores=[0.05, 0.1, 0.2, 0.5, 0.6, 0.8, 0.9, 0.95],
        ),
    )

    assert cli.main(["filter"]) == 0
    assert seen["provider"] is stub_provider
    assert (
        "Scored 8: 3 relevant, 5 irrelevant (1 refused, 4 errors, 2 borderline)"
        in capsys.readouterr().out
    )


@pytest.mark.parametrize("run_id", [42, 99])
def test_filter_attaches_its_own_run_id_with_tracking_active_throughout(
    db_session, stub_provider, monkeypatch, run_id
):
    """Two ids, so a hardcoded constant in cli.py fails one of them. `tracked`
    pins the pipeline call inside the block and the tuple's flag pins the
    attach inside it - the two ways the correlation can silently break."""
    calls = _capture_attach(monkeypatch)
    seen = _run_filter(monkeypatch, FilterReport(relevant=1, run_id=run_id))

    assert cli.main(["filter"]) == 0
    assert seen["tracked"] is True
    assert calls == [(run_id, True)]


def test_filter_attaches_nothing_when_telemetry_opened_no_run(
    db_session, stub_provider, monkeypatch, capsys
):
    """run_id is None when open_run() itself failed - swallowed upstream. The
    run still has to report itself and succeed."""
    calls = _capture_attach(monkeypatch)
    _run_filter(monkeypatch, FilterReport(relevant=1, run_id=None))

    assert cli.main(["filter"]) == 0
    assert calls == []
    assert "Scored 1:" in capsys.readouterr().out


def test_filter_still_succeeds_when_attaching_the_run_id_fails(
    db_session, stub_provider, monkeypatch, caplog
):
    """Log correlation is a convenience - losing it must not fail the run
    that already scored articles."""
    _break_attach(monkeypatch)
    _run_filter(monkeypatch, FilterReport(relevant=1, run_id=42))

    with caplog.at_level(logging.WARNING, logger="newsagent.cli"):
        assert cli.main(["filter"]) == 0

    assert "Failed to attach outbound_run_id=42" in caplog.text


def test_summarize_prints_every_report_number_in_its_own_slot(
    db_session, stub_provider, monkeypatch, capsys
):
    seen = _run_summarize(monkeypatch, SummarizeReport(summarized=7, refused=1, errors=2))

    assert cli.main(["summarize"]) == 0
    assert seen["provider"] is stub_provider
    assert "Summarized 7 (1 refused, 2 errors)" in capsys.readouterr().out


@pytest.mark.parametrize("run_id", [7, 13])
def test_summarize_attaches_its_own_run_id_with_tracking_active_throughout(
    db_session, stub_provider, monkeypatch, run_id
):
    calls = _capture_attach(monkeypatch)
    seen = _run_summarize(monkeypatch, SummarizeReport(summarized=1, run_id=run_id))

    assert cli.main(["summarize"]) == 0
    assert seen["tracked"] is True
    assert calls == [(run_id, True)]


def test_summarize_attaches_nothing_when_telemetry_opened_no_run(
    db_session, stub_provider, monkeypatch, capsys
):
    """The same guard as filter's, in a separate dispatch branch - dropping
    this one would not fail filter's test."""
    calls = _capture_attach(monkeypatch)
    _run_summarize(monkeypatch, SummarizeReport(summarized=1, run_id=None))

    assert cli.main(["summarize"]) == 0
    assert calls == []
    assert "Summarized 1" in capsys.readouterr().out


def test_summarize_still_succeeds_when_attaching_the_run_id_fails(
    db_session, stub_provider, monkeypatch, caplog
):
    _break_attach(monkeypatch)
    _run_summarize(monkeypatch, SummarizeReport(summarized=1, run_id=7))

    with caplog.at_level(logging.WARNING, logger="newsagent.cli"):
        assert cli.main(["summarize"]) == 0

    assert "Failed to attach outbound_run_id=7" in caplog.text


# --- `subscribe`: the only command with a non-zero exit path ------------------


def test_subscribe_reports_a_new_subscription(db_session, monkeypatch, capsys):
    monkeypatch.setattr(cli.preferences, "subscribe", lambda db, email, topic: (object(), True))

    assert cli.main(["subscribe", "reader@example.com", "AI"]) == 0
    assert "Subscribed: reader@example.com -> AI" in capsys.readouterr().out


def test_subscribe_is_idempotent_and_says_so(db_session, monkeypatch, capsys):
    monkeypatch.setattr(cli.preferences, "subscribe", lambda db, email, topic: (object(), False))

    assert cli.main(["subscribe", "reader@example.com", "AI"]) == 0
    assert "Already subscribed: reader@example.com -> AI" in capsys.readouterr().out


def test_subscribe_passes_its_two_arguments_in_the_right_order(db_session, monkeypatch):
    """Both are positional strings of the same type, so a swap type-checks,
    runs, and prints a correct-looking line built from argv rather than from
    what the service actually received."""
    seen: dict = {}

    def fake(db, email, topic):
        seen["email"], seen["topic"] = email, topic
        return object(), True

    monkeypatch.setattr(cli.preferences, "subscribe", fake)

    cli.main(["subscribe", "reader@example.com", "AI"])
    assert seen == {"email": "reader@example.com", "topic": "AI"}


def test_subscribe_exits_non_zero_when_the_target_does_not_exist(db_session, monkeypatch, capsys):
    """An operator script branches on this exit code, so a bad email or an
    unknown topic must not look like success."""

    def boom(db, email, topic):
        raise ValueError("no such topic: Quantum")

    monkeypatch.setattr(cli.preferences, "subscribe", boom)

    assert cli.main(["subscribe", "reader@example.com", "Quantum"]) == 1
    assert "Error: no such topic: Quantum" in capsys.readouterr().out


# --- `fetch`: the only per-item formatting in the file ------------------------


def test_fetch_prints_counts_per_source_and_a_total(db_session, monkeypatch, capsys):
    """Distinct new/duplicate values, so a transposed pair fails."""
    monkeypatch.setattr(
        cli.fetcher,
        "fetch_approved_sources",
        lambda db: FetchReport(
            results=[
                SourceResult(source_name="TechCrunch", new_articles=3, duplicates=7),
                SourceResult(source_name="SpaceNews", new_articles=2, duplicates=9),
            ]
        ),
    )

    assert cli.main(["fetch"]) == 0
    out = capsys.readouterr().out
    assert "TechCrunch: 3 new, 7 known" in out
    assert "SpaceNews: 2 new, 9 known" in out
    assert "Total new articles: 5" in out


def test_fetch_prints_a_failing_source_as_an_error_not_as_zero_articles(
    db_session, monkeypatch, capsys
):
    """A dead feed has to be visibly different from a feed with no news."""
    monkeypatch.setattr(
        cli.fetcher,
        "fetch_approved_sources",
        lambda db: FetchReport(
            results=[SourceResult(source_name="Krebs", error="connection refused")]
        ),
    )

    assert cli.main(["fetch"]) == 0
    out = capsys.readouterr().out
    assert "Krebs: ERROR: connection refused" in out
    assert "Krebs: 0 new" not in out


def test_fetch_with_no_approved_sources_still_reports_a_total(db_session, monkeypatch, capsys):
    """Nothing to iterate is a real state (a fresh install before seed-sources).
    Without the total line it would be indistinguishable from a broken loop."""
    monkeypatch.setattr(cli.fetcher, "fetch_approved_sources", lambda db: FetchReport())

    assert cli.main(["fetch"]) == 0
    assert "Total new articles: 0" in capsys.readouterr().out


# --- `send-digests`: two passes, and the pairing lives only here --------------


def test_send_digests_also_sends_the_owed_welcomes(db_session, monkeypatch, capsys):
    """A reader whose topics produced nothing still gets their one-time
    welcome. Dropping the second pass would silence them without failing any
    other test on this path. Both passes run in order and share the single
    sender this command builds - the factory counts its calls, so a second
    sender built for the welcome pass fails rather than comparing equal."""
    built: list[object] = []
    passes: list[tuple[str, object]] = []

    def build_sender():
        sender = object()
        built.append(sender)
        return sender

    monkeypatch.setattr(cli, "get_email_sender", build_sender)

    def fake_digests(db, passed_sender):
        passes.append(("digests", passed_sender))
        return SendReport(sent=4, failed=1)

    def fake_welcomes(db, passed_sender):
        passes.append(("welcomes", passed_sender))
        return SendReport(sent=2, failed=3)

    monkeypatch.setattr(cli.send, "send_pending_digests", fake_digests)
    monkeypatch.setattr(cli.send, "send_pending_welcomes", fake_welcomes)

    assert cli.main(["send-digests"]) == 0
    assert len(built) == 1
    assert passes == [("digests", built[0]), ("welcomes", built[0])]
    out = capsys.readouterr().out
    assert "Sent 4, failed 1" in out
    assert "Welcome-only: sent 2, failed 3" in out


# --- thin commands: one service call, one printed line ------------------------
#
# Each of these is a pass-through whose service is covered by its own tests. The
# stub takes `db` explicitly so a dropped session is a TypeError here rather
# than only in production, and ignores the rest - which is why the argv-carrying
# commands get their own passthrough tests below. The identity rows feed argv an
# un-normalized email while the stub returns the normalized one, so the printed
# line is pinned to the persisted record rather than to what was typed.


@pytest.mark.parametrize(
    ("argv", "module", "attr", "result", "expected"),
    [
        (
            ["add-admin", "Boss@Example.COM"],
            "identity",
            "add_admin",
            (SimpleNamespace(email="boss@example.com", id=1), True),
            "Created: admin boss@example.com (id=1)",
        ),
        (
            ["add-admin", "Boss@Example.COM"],
            "identity",
            "add_admin",
            (SimpleNamespace(email="boss@example.com", id=1), False),
            "Already exists: admin boss@example.com (id=1)",
        ),
        (
            ["add-user", "Reader@Example.COM", "--name", "Reader"],
            "identity",
            "add_user",
            (SimpleNamespace(email="reader@example.com", id=2), True),
            "Created: user reader@example.com (id=2)",
        ),
        (
            ["add-user", "Reader@Example.COM", "--name", "Reader"],
            "identity",
            "add_user",
            (SimpleNamespace(email="reader@example.com", id=2), False),
            "Already exists: user reader@example.com (id=2)",
        ),
        (
            ["seed-sources"],
            "sources",
            "seed_default_sources",
            SimpleNamespace(topics_created=3, sources_created=8),
            "Seeded: 3 new topics, 8 new sources",
        ),
        (
            ["seed-fields"],
            "taxonomy",
            "seed_default_fields",
            SimpleNamespace(fields_created=5),
            "Seeded: 5 new fields",
        ),
        (
            ["seed-roles"],
            "taxonomy",
            "seed_default_roles",
            SimpleNamespace(fields_created=1, roles_created=9),
            "Seeded: 1 new fields, 9 new roles",
        ),
        (
            ["extract"],
            "extract",
            "extract_relevant_articles",
            ExtractReport(extracted=6, failed=2),
            "Extracted 6, failed 2",
        ),
    ],
    ids=[
        "add-admin-created",
        "add-admin-exists",
        "add-user-created",
        "add-user-exists",
        "seed-sources",
        "seed-fields",
        "seed-roles",
        "extract",
    ],
)
def test_thin_command_prints_its_report(
    db_session, monkeypatch, capsys, argv, module, attr, result, expected
):
    monkeypatch.setattr(getattr(cli, module), attr, lambda db, *a, **k: result)

    assert cli.main(argv) == 0
    assert expected in capsys.readouterr().out


def test_add_admin_passes_the_email_through(db_session, monkeypatch):
    """The sweep above cannot catch this: its stub ignores this argument, so
    the expected line comes from the stub rather than from argv."""
    seen: dict = {}

    def fake(db, email):
        seen["email"] = email
        return SimpleNamespace(email=email, id=1), True

    monkeypatch.setattr(cli.identity, "add_admin", fake)

    cli.main(["add-admin", "boss@example.com"])
    assert seen == {"email": "boss@example.com"}


def test_add_user_passes_the_optional_name_through(db_session, monkeypatch):
    """--name is the one optional argument on these commands, so it is the one
    that can silently stop reaching its service."""
    seen: dict = {}

    def fake(db, email, name):
        seen["email"], seen["name"] = email, name
        return SimpleNamespace(email=email, id=1), True

    monkeypatch.setattr(cli.identity, "add_user", fake)

    cli.main(["add-user", "reader@example.com", "--name", "Full Name"])
    assert seen == {"email": "reader@example.com", "name": "Full Name"}

    seen.clear()
    cli.main(["add-user", "reader@example.com"])
    assert seen == {"email": "reader@example.com", "name": None}


def test_build_digests_prints_its_three_counts(db_session, stub_provider, monkeypatch, capsys):
    seen: dict = {}

    def fake(db, provider):
        seen["provider"] = provider
        return DigestReport(users_processed=4, digests_created=3, articles_added=11)

    monkeypatch.setattr(cli.digest, "build_digests", fake)

    assert cli.main(["build-digests"]) == 0
    assert seen["provider"] is stub_provider
    assert "Users: 4, digests created: 3, articles added: 11" in capsys.readouterr().out
