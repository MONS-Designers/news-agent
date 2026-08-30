"""Coverage for telemetry/pricing.py: `lookup_rate` (read side, used by
services/telemetry.py::record_call) and `refresh_from_openrouter` (the one
place OpenRouter's response shape is known, per AD-21).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from newsagent.config import settings
from newsagent.models import ModelPrice
from newsagent.models.base import Base
from newsagent.telemetry import pricing


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False)
    with session_local() as session:
        yield session


@pytest.fixture(autouse=True)
def _tracked_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh_from_openrouter only prices models the project actually calls
    (the two configured adapters) - most tests exercise those two; a test
    that needs a different model on the tracked list overrides this."""
    monkeypatch.setattr(settings, "external_llm_model", "z-ai/glm-5.2")
    monkeypatch.setattr(settings, "local_llm_model", "anthropic/claude-opus-5")


def _models_response(*entries: dict) -> httpx.Response:
    # raise_for_status() requires a request to be attached (it errors on that
    # check before even looking at the status code) - real traffic gets one
    # for free from the Client that sent it; a directly-constructed Response
    # needs it set explicitly.
    return httpx.Response(
        200,
        json={"data": list(entries)},
        request=httpx.Request("GET", "https://openrouter.ai/api/v1/models"),
    )


def _entry(model: str, prompt: str, completion: str) -> dict:
    return {"id": model, "pricing": {"prompt": prompt, "completion": completion}}


# -- lookup_rate ---------------------------------------------------------


def test_lookup_rate_returns_none_when_never_priced(db):
    assert pricing.lookup_rate(db, "z-ai/glm-5.2") is None


def test_lookup_rate_returns_the_latest_effective_row(db):
    db.add_all(
        [
            ModelPrice(
                model="z-ai/glm-5.2",
                rate_in_usd_per_mtok=Decimal("0.100000"),
                rate_out_usd_per_mtok=Decimal("0.400000"),
                effective_from=datetime.now(UTC) - timedelta(days=7),
                source="api",
            ),
            ModelPrice(
                model="z-ai/glm-5.2",
                rate_in_usd_per_mtok=Decimal("0.150000"),
                rate_out_usd_per_mtok=Decimal("0.450000"),
                effective_from=datetime.now(UTC),
                source="api",
            ),
        ]
    )
    db.commit()

    assert pricing.lookup_rate(db, "z-ai/glm-5.2") == (Decimal("0.150000"), Decimal("0.450000"))


# -- refresh_from_openrouter ----------------------------------------------


def test_refresh_inserts_a_row_per_priced_model(db, monkeypatch):
    monkeypatch.setattr(
        pricing.httpx,
        "get",
        lambda url, timeout: _models_response(
            _entry("z-ai/glm-5.2", "0.0000001", "0.0000004"),
            _entry("anthropic/claude-opus-5", "0.000005", "0.000025"),
        ),
    )

    result = pricing.refresh_from_openrouter(db)

    assert result.updated == 2
    assert pricing.lookup_rate(db, "z-ai/glm-5.2") == (Decimal("0.100000"), Decimal("0.400000"))
    assert pricing.lookup_rate(db, "anthropic/claude-opus-5") == (
        Decimal("5.000000"),
        Decimal("25.000000"),
    )


def test_refresh_only_prices_tracked_models(db, monkeypatch):
    """OpenRouter lists hundreds of models; this project only ever calls the
    two configured in settings (external_llm_model / local_llm_model) - an
    untracked model must be skipped even though its pricing is perfectly
    usable."""
    monkeypatch.setattr(
        pricing.httpx,
        "get",
        lambda url, timeout: _models_response(
            _entry("z-ai/glm-5.2", "0.0000001", "0.0000004"),
            _entry("some/unrelated-model", "0.000001", "0.000002"),
        ),
    )

    result = pricing.refresh_from_openrouter(db)

    assert result.updated == 1
    assert pricing.lookup_rate(db, "z-ai/glm-5.2") is not None
    assert pricing.lookup_rate(db, "some/unrelated-model") is None


def test_refresh_does_nothing_and_skips_the_fetch_when_nothing_is_tracked(db, monkeypatch):
    monkeypatch.setattr(settings, "external_llm_model", "")
    monkeypatch.setattr(settings, "local_llm_model", "")

    def _fail(url, timeout):
        raise AssertionError("should not fetch when there is nothing to price")

    monkeypatch.setattr(pricing.httpx, "get", _fail)

    assert pricing.refresh_from_openrouter(db) == pricing.RefreshResult(updated=0)


def test_refresh_skips_variable_pricing_sentinel(db, monkeypatch):
    """OpenRouter marks no-fixed-price models (e.g. its "auto" router) with a
    literal "-1" token price - observed in production, where it overflowed
    the Numeric(12, 6) column outright rather than just being a bad price."""
    monkeypatch.setattr(settings, "external_llm_model", "openrouter/auto-beta")
    monkeypatch.setattr(
        pricing.httpx,
        "get",
        lambda url, timeout: _models_response(_entry("openrouter/auto-beta", "-1", "-1")),
    )

    result = pricing.refresh_from_openrouter(db)

    assert result.updated == 0
    assert pricing.lookup_rate(db, "openrouter/auto-beta") is None


def test_refresh_skips_entries_without_usable_pricing(db, monkeypatch):
    monkeypatch.setattr(settings, "external_llm_model", "no-pricing-field/model")
    monkeypatch.setattr(settings, "local_llm_model", "bad-shape/model")
    monkeypatch.setattr(
        pricing.httpx,
        "get",
        lambda url, timeout: _models_response(
            {"id": "no-pricing-field/model"},
            {"id": "bad-shape/model", "pricing": "not-a-dict"},
            {"pricing": {"prompt": "0.0000001", "completion": "0.0000004"}},  # no id
        ),
    )

    result = pricing.refresh_from_openrouter(db)

    assert result.updated == 0
    assert pricing.lookup_rate(db, "no-pricing-field/model") is None


def test_refresh_does_not_reinsert_an_unchanged_rate(db, monkeypatch):
    entry = _entry("z-ai/glm-5.2", "0.0000001", "0.0000004")
    monkeypatch.setattr(pricing.httpx, "get", lambda url, timeout: _models_response(entry))

    first = pricing.refresh_from_openrouter(db)
    second = pricing.refresh_from_openrouter(db)

    assert first.updated == 1
    assert second.updated == 0
    assert db.query(ModelPrice).count() == 1


def test_refresh_adds_a_new_row_when_the_rate_changes_keeping_the_old_one(db, monkeypatch):
    responses = iter(
        [
            _models_response(_entry("z-ai/glm-5.2", "0.0000001", "0.0000004")),
            _models_response(_entry("z-ai/glm-5.2", "0.0000002", "0.0000004")),
        ]
    )
    monkeypatch.setattr(pricing.httpx, "get", lambda url, timeout: next(responses))

    pricing.refresh_from_openrouter(db)
    second = pricing.refresh_from_openrouter(db)

    assert second.updated == 1
    assert db.query(ModelPrice).count() == 2
    assert pricing.lookup_rate(db, "z-ai/glm-5.2") == (Decimal("0.200000"), Decimal("0.400000"))


def test_refresh_propagates_transport_failure_instead_of_swallowing_it(db, monkeypatch):
    def _raise(url, timeout):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(pricing.httpx, "get", _raise)

    with pytest.raises(httpx.ConnectError):
        pricing.refresh_from_openrouter(db)

    assert db.query(ModelPrice).count() == 0


def test_refresh_propagates_http_error_status(db, monkeypatch):
    monkeypatch.setattr(
        pricing.httpx,
        "get",
        lambda url, timeout: httpx.Response(
            503,
            json={"error": "down"},
            request=httpx.Request("GET", "https://openrouter.ai/api/v1/models"),
        ),
    )

    with pytest.raises(httpx.HTTPStatusError):
        pricing.refresh_from_openrouter(db)
