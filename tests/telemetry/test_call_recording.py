"""End-to-end coverage of the spec's frozen I/O & Edge-Case Matrix and its
Acceptance Criteria: measurer (http_llm_client) -> ambient context
(telemetry/context.py) -> sole writer (services/telemetry.py), exercised
through the real ExternalLLMProvider + httpx.MockTransport (no network) so
the whole chain runs, not just one layer in isolation.

`telemetry_db` (tests/conftest.py) is the same in-memory sqlite the autouse
`_isolate_telemetry_from_real_db` fixture already points telemetry.sink at
for every test in the suite - it's requested explicitly here to read back
what got written.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent import telemetry
from newsagent.config import settings
from newsagent.http_llm_client import send_chat_completion
from newsagent.llm.errors import LLMProviderError
from newsagent.llm.external import ExternalLLMProvider
from newsagent.llm.types import ArticleInput
from newsagent.models import (
    Article,
    Field,
    OutboundCall,
    OutboundRun,
    Role,
    Source,
    Topic,
    User,
    UserTopicPreference,
)
from newsagent.models.base import Base
from newsagent.pipeline.relevance import filter_pending_articles
from newsagent.services import profile as profile_service
from newsagent.services import taxonomy as taxonomy_service
from newsagent.suggestions.errors import SuggestionProviderError
from newsagent.suggestions.llm import LLMSuggestionSource

ARTICLE = ArticleInput(title="An article", text="a" * 60)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "external_llm_base_url", "http://external-model.test")
    monkeypatch.setattr(settings, "external_llm_auth_token", "test-token")
    monkeypatch.setattr(settings, "external_llm_model", "test-model")
    monkeypatch.setattr(settings, "local_llm_base_url", "http://local-model.test")
    monkeypatch.setattr(settings, "local_llm_auth_token", "test-token")
    monkeypatch.setattr(settings, "local_llm_model", "test-model")


def _provider(handler) -> ExternalLLMProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ExternalLLMProvider(client=client, sleep=lambda _: None)


def _suggestion_source(handler) -> LLMSuggestionSource:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMSuggestionSource(client=client, sleep=lambda _: None)


def _read(telemetry_db) -> tuple[list[OutboundRun], list[OutboundCall]]:
    with telemetry_db() as db:
        runs = db.scalars(select(OutboundRun)).all()
        calls = db.scalars(select(OutboundCall)).all()
        return runs, calls


def _ok_response(score: float = 0.9) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": f'{{"score": {score}}}'}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 7},
        },
    )


# -- "Successful call" row of the matrix -------------------------------------


def test_successful_call_is_recorded_with_real_tokens_and_null_cost(telemetry_db):
    provider = _provider(lambda request: _ok_response())

    with telemetry.open_run(telemetry.KIND_FILTER, subscriber_count=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_FILTERING, article_id=4711):
            provider.score_relevance(ARTICLE, "topic")
        run.close(succeeded=1)

    runs, calls = _read(telemetry_db)
    assert len(runs) == 1
    assert len(calls) == 1
    call = calls[0]
    assert call.purpose == "FILTERING"
    assert call.article_id == 4711
    assert call.attempt == 1
    assert call.status == "ok"
    assert call.tokens_in == 42
    assert call.tokens_out == 7
    assert call.duration_ms is not None and call.duration_ms >= 0
    assert call.cost_usd is None
    assert call.run_id == run.run_id


# -- "Retry" row of the matrix ------------------------------------------------


def test_retry_produces_two_rows_same_run_and_article_increasing_attempt(telemetry_db):
    responses = iter([httpx.Response(408, json={"error": "timeout"}), _ok_response()])
    provider = _provider(lambda request: next(responses))

    with telemetry.open_run(telemetry.KIND_FILTER, subscriber_count=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_FILTERING, article_id=99):
            provider.score_relevance(ARTICLE, "topic")

    _, calls = _read(telemetry_db)
    assert len(calls) == 2
    assert {c.run_id for c in calls} == {run.run_id}
    assert {c.article_id for c in calls} == {99}
    by_attempt = {c.attempt: c for c in calls}
    assert set(by_attempt) == {1, 2}
    assert by_attempt[1].status == "error"
    assert by_attempt[2].status == "ok"


# -- "Cache hit" row of the matrix --------------------------------------------


def test_avoided_call_has_zero_cost_null_tokens_and_real_duration(telemetry_db):
    with telemetry.open_run(telemetry.KIND_DIGEST_BUILD, user_id=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_DIGEST_VOICE):
            telemetry.report_avoided(duration_ms=12)
        run.close(succeeded=1)

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    call = calls[0]
    assert call.status == "avoided"
    assert call.tokens_in is None
    assert call.tokens_out is None
    assert call.cost_usd == Decimal("0")
    assert call.duration_ms == 12


# -- "Junk refusal" row of the matrix, plus Acceptance Criterion #1 ----------


@pytest.fixture
def pipeline_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="artificial intelligence")
        session.add(topic)
        session.flush()
        session.add(
            Source(id=1, topic_id=topic.id, name="Approved", url="feed://ok", status="approved")
        )
        user = User(email="user@example.com")
        session.add(user)
        session.flush()
        session.add(UserTopicPreference(user_id=user.id, topic_id=topic.id))
        session.commit()
        yield session


def _add_article(db: Session, *, url_suffix: str, summary: str | None) -> Article:
    article = Article(
        source_id=1,
        title="Some article title",
        url=f"https://example.com/{url_suffix}",
        rss_summary=summary,
        relevance_status="pending",
    )
    db.add(article)
    db.commit()
    return article


def _unexpected_network_call(request: httpx.Request) -> httpx.Response:
    raise AssertionError("no network call expected - junk text must be refused before it")


def test_junk_refusal_writes_no_call_row_and_increments_run_refused(pipeline_db, telemetry_db):
    _add_article(pipeline_db, url_suffix="junk", summary="tiny")
    provider = _provider(_unexpected_network_call)

    report = filter_pending_articles(pipeline_db, provider)

    assert report.refused == 1
    runs, calls = _read(telemetry_db)
    assert len(runs) == 1
    assert runs[0].refused == 1
    assert runs[0].succeeded == 0
    assert calls == []


def test_filter_run_over_five_articles_writes_one_run_and_five_calls_with_article_id(
    pipeline_db, telemetry_db
):
    """Acceptance Criterion #1."""
    for i in range(5):
        _add_article(pipeline_db, url_suffix=str(i), summary="a" * 60)
    provider = _provider(lambda request: _ok_response())

    report = filter_pending_articles(pipeline_db, provider)

    assert report.scored == 5
    runs, calls = _read(telemetry_db)
    assert len(runs) == 1
    assert len(calls) == 5
    assert all(c.article_id is not None for c in calls)
    assert all(c.run_id == runs[0].id for c in calls)
    assert all(c.status == "ok" for c in calls)


# -- "No context" row of the matrix, plus Acceptance Criterion #2 -----------


def test_call_with_no_open_context_is_recorded_as_unattributed_and_does_not_raise(telemetry_db):
    send_chat_completion(
        base_url="http://external-model.test",
        auth_token="t",
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        client=httpx.Client(transport=httpx.MockTransport(lambda request: _ok_response())),
    )

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    call = calls[0]
    assert call.purpose == "UNATTRIBUTED"
    assert call.article_id is None
    assert call.run_id is None
    assert call.duration_ms is not None
    assert call.model == "test-model"


# -- "Call from a thread" row of the matrix ----------------------------------


def test_thread_call_carries_the_calling_threads_run_id_via_copy_context(telemetry_db):
    """Mirrors services/profile.py's fix: contextvars do not cross into a
    ThreadPoolExecutor worker on their own - copy_context()+ctx.run is
    required, or every call from the worker silently records UNATTRIBUTED."""
    client = httpx.Client(transport=httpx.MockTransport(lambda request: _ok_response()))

    with telemetry.open_run(telemetry.KIND_PROFILE_SUGGESTIONS, user_id=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_SUGGEST_TOPICS):
            ctx = copy_context()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    ctx.run,
                    send_chat_completion,
                    base_url="http://external-model.test",
                    auth_token="t",
                    model="test-model",
                    messages=[{"role": "user", "content": "hi"}],
                    client=client,
                )
                future.result()
        run.close(succeeded=1)

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    assert calls[0].run_id == run.run_id
    assert calls[0].purpose == "SUGGEST_TOPICS"


def test_thread_call_without_copy_context_falls_back_to_unattributed_not_a_crash(telemetry_db):
    """The negative case named in the matrix: if context did not propagate,
    the call is UNATTRIBUTED - never a crash."""
    client = httpx.Client(transport=httpx.MockTransport(lambda request: _ok_response()))

    with telemetry.open_run(telemetry.KIND_PROFILE_SUGGESTIONS, user_id=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_SUGGEST_TOPICS):
            with ThreadPoolExecutor(max_workers=1) as pool:
                # Deliberately submitted WITHOUT copy_context().run - the
                # worker thread starts with a fresh, empty context.
                future = pool.submit(
                    send_chat_completion,
                    base_url="http://external-model.test",
                    auth_token="t",
                    model="test-model",
                    messages=[{"role": "user", "content": "hi"}],
                    client=client,
                )
                future.result()  # must not raise
        run.close(succeeded=1)

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    assert calls[0].purpose == "UNATTRIBUTED"
    assert calls[0].run_id is None


# -- "Write failure" row of the matrix ---------------------------------------


def test_db_write_failure_is_swallowed_and_logged_and_business_op_still_completes(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    def _broken_session_local():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("newsagent.telemetry.sink.SessionLocal", _broken_session_local)
    provider = _provider(lambda request: _ok_response())

    with caplog.at_level(logging.ERROR, logger="newsagent.telemetry.sink"):
        result = provider.score_relevance(ARTICLE, "topic")

    assert result.score == 0.9  # the business operation completed normally
    assert any(record.levelno == logging.ERROR for record in caplog.records)


# -- "Billed but unusable" row of the matrix (malformed status) -------------
# Spec Change Log 2026-08-27: a call that billed real tokens but whose body
# failed parsing/schema validation must record status='malformed', never
# 'ok' - on BOTH the llm/ path (llm/external.py) and the sibling suggestions/
# path (suggestions/llm.py), since AD-3 keeps their retry loops separate.


def test_malformed_output_on_the_llm_path_is_recorded_with_real_tokens_never_ok(telemetry_db):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "not valid json at all"}}],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45},
            },
        )

    provider = _provider(handler)
    with telemetry.open_run(telemetry.KIND_FILTER, subscriber_count=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_FILTERING, article_id=1):
            with pytest.raises(LLMProviderError):
                provider.score_relevance(ARTICLE, "topic")

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    call = calls[0]
    assert call.status == "malformed"
    assert call.status != "ok"
    assert call.tokens_in == 123
    assert call.tokens_out == 45
    assert call.duration_ms is not None
    assert call.run_id == run.run_id


def test_malformed_output_on_the_suggestions_path_is_recorded_with_real_tokens_never_ok(
    telemetry_db,
):
    """Same guarantee as above, through suggestions/llm.py + suggestions/base.py's
    own separate retry loop (AD-3: no cross-import with llm/, so this is a
    distinct code path that needed its own fix)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "not valid json at all"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    source = _suggestion_source(handler)
    with telemetry.open_run(telemetry.KIND_TAXONOMY_SUGGESTION, user_id=None) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_SUGGEST_ROLES):
            with pytest.raises(SuggestionProviderError):
                source.suggest_roles("Tech")

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    call = calls[0]
    assert call.status == "malformed"
    assert call.status != "ok"
    assert call.tokens_in == 10
    assert call.tokens_out == 2
    assert call.run_id == run.run_id


# Review Finding, 2026-08-27: a response whose body isn't JSON at all (an
# HTML error page from a proxy, say) fails inside http_llm_client BEFORE any
# usage block is ever parsed - nothing was billed. This must stay 'error',
# never 'malformed' (AD-15: malformed implies real tokens were billed).


def test_non_json_body_on_the_llm_path_stays_error_not_malformed_with_null_tokens(
    telemetry_db,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json at all</html>")

    provider = _provider(handler)
    with telemetry.open_run(telemetry.KIND_FILTER, subscriber_count=1) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_FILTERING, article_id=1):
            with pytest.raises(LLMProviderError):
                provider.score_relevance(ARTICLE, "topic")

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    call = calls[0]
    assert call.status == "error"
    assert call.status != "malformed"
    assert call.tokens_in is None
    assert call.tokens_out is None
    assert call.run_id == run.run_id


def test_non_json_body_on_the_suggestions_path_stays_error_not_malformed_with_null_tokens(
    telemetry_db,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json at all</html>")

    source = _suggestion_source(handler)
    with telemetry.open_run(telemetry.KIND_TAXONOMY_SUGGESTION, user_id=None) as run:
        with telemetry.attribute_call(telemetry.PURPOSE_SUGGEST_ROLES):
            with pytest.raises(SuggestionProviderError):
                source.suggest_roles("Tech")

    _, calls = _read(telemetry_db)
    assert len(calls) == 1
    call = calls[0]
    assert call.status == "error"
    assert call.status != "malformed"
    assert call.tokens_in is None
    assert call.tokens_out is None
    assert call.run_id == run.run_id


def test_suggestions_retry_now_increments_attempt(telemetry_db):
    """First-pass regression: suggestions/base.py's _run never called
    increment_attempt(), so every retried suggestion call recorded attempt=1
    twice instead of 1 then 2. Fixed alongside the malformed-status rework
    since both live in the same _run."""
    responses = iter([httpx.Response(408, json={"error": "timeout"}), _ok_ish_roles_response()])

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    source = _suggestion_source(handler)
    with telemetry.open_run(telemetry.KIND_TAXONOMY_SUGGESTION, user_id=None):
        with telemetry.attribute_call(telemetry.PURPOSE_SUGGEST_ROLES):
            source.suggest_roles("Tech")

    _, calls = _read(telemetry_db)
    assert len(calls) == 2
    assert {c.attempt for c in calls} == {1, 2}
    by_attempt = {c.attempt: c for c in calls}
    assert by_attempt[1].status == "error"
    assert by_attempt[2].status == "ok"


def _ok_ish_roles_response() -> httpx.Response:
    import json as _json

    return httpx.Response(
        200, json={"choices": [{"message": {"content": _json.dumps({"roles": ["Backend"]})}}]}
    )


# -- Amendment 2026-08-27: the two suggestion call sites missed by the first
# pass (services/profile.py's suggest_prompts_for_user, services/taxonomy.py's
# suggest_roles_for_field) must now open their own run instead of recording
# as UNATTRIBUTED forever.


@pytest.fixture
def taxonomy_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        field = Field(name="Tech")
        session.add(field)
        session.commit()
        yield session


def _ok_prompts_response(request: httpx.Request) -> httpx.Response:
    import json as _json

    return httpx.Response(
        200, json={"choices": [{"message": {"content": _json.dumps({"prompts": ["x"]})}}]}
    )


def test_suggest_prompts_for_user_opens_a_run_with_the_users_id(monkeypatch, telemetry_db):
    user = User(id=7, email="u@example.com", field_name="Tech")
    source = _suggestion_source(_ok_prompts_response)
    monkeypatch.setattr(profile_service, "get_suggestion_source", lambda: source)

    profile_service.suggest_prompts_for_user(user)

    runs, calls = _read(telemetry_db)
    assert len(runs) == 1
    # Its own kind, distinct from _compute_and_store_suggestions'
    # KIND_PROFILE_SUGGESTIONS (Review Finding, 2026-08-27): one cheap
    # read-only lookup vs two concurrent LLM calls plus a DB write.
    assert runs[0].kind == telemetry.KIND_PROMPT_SUGGESTIONS
    assert runs[0].user_id == 7
    # suggest_prompts issues a real call through the transport (unlike the
    # popularity fallback), so the wiring must attribute it - not UNATTRIBUTED.
    assert len(calls) == 1
    assert calls[0].purpose == telemetry.PURPOSE_SUGGEST_PROMPTS
    assert calls[0].run_id == runs[0].id


def test_suggest_roles_for_field_opens_a_run_with_no_user(
    monkeypatch, taxonomy_db, telemetry_db
):
    field = taxonomy_db.scalar(select(Field))

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        return httpx.Response(
            200, json={"choices": [{"message": {"content": _json.dumps({"roles": []})}}]}
        )

    source = _suggestion_source(handler)
    monkeypatch.setattr(taxonomy_service, "get_suggestion_source", lambda: source)

    taxonomy_service.suggest_roles_for_field(taxonomy_db, field)

    runs, calls = _read(telemetry_db)
    assert len(runs) == 1
    assert runs[0].kind == telemetry.KIND_TAXONOMY_SUGGESTION
    assert runs[0].user_id is None
    assert len(calls) == 1
    assert calls[0].purpose == telemetry.PURPOSE_SUGGEST_ROLES
    assert calls[0].run_id == runs[0].id


def test_suggest_roles_for_field_still_opens_a_run_when_curated_roles_fill_the_cap(
    taxonomy_db, telemetry_db
):
    """Review Finding, 2026-08-27: when the curated catalog already fills
    ROLE_SUGGESTION_CAP, the function used to return before ever reaching
    open_run() - zero outbound_runs rows, contradicting AD-13's "a run row
    is always created" - even though no LLM call is made or needed."""
    field = taxonomy_db.scalar(select(Field))
    for i in range(taxonomy_service.ROLE_SUGGESTION_CAP):
        taxonomy_db.add(Role(field_id=field.id, name=f"Role {i}"))
    taxonomy_db.commit()

    views = taxonomy_service.suggest_roles_for_field(taxonomy_db, field)

    assert len(views) == taxonomy_service.ROLE_SUGGESTION_CAP
    runs, calls = _read(telemetry_db)
    assert len(runs) == 1
    assert runs[0].kind == telemetry.KIND_TAXONOMY_SUGGESTION
    assert runs[0].succeeded == 1
    assert runs[0].errors == 0
    assert calls == []  # no LLM call was made or needed
