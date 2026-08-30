"""Model pricing lookup and refresh (ARCHITECTURE-SPINE AD-16, AD-21).

`lookup_rate` is read by `services/telemetry.py::record_call` on every
priced call - it never talks to a provider, only `model_prices`.

`refresh_from_openrouter` is the one function in this codebase that knows
OpenRouter's response shape. The pricing source is pinned via
`EXTERNAL_LLM_BASE_URL` rather than a hardcoded host, per the confirmed
dev/prod config - but the parsing below is still OpenRouter-specific: a
future provider swap means rewriting this one function's body, nothing
else here or in its callers.
"""

from dataclasses import dataclass
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import ModelPrice

_FETCH_TIMEOUT_SECONDS = 10.0
# OpenRouter quotes $/token; outbound_calls.rate_*_usd_per_mtok is $/million
# tokens (AD-16) - convert once, here, so no caller has to know the source unit.
_USD_PER_TOKEN_TO_USD_PER_MTOK = Decimal(1_000_000)
# Matches the Numeric(12, 6) column scale, so a freshly computed rate compares
# equal to one already round-tripped through the DB (see the dedup check below).
_RATE_QUANTUM = Decimal("0.000001")
# Numeric(12, 6)'s own ceiling - a $/Mtok rate can never legitimately reach
# this. OpenRouter marks variable/no-fixed-price models (e.g. its own
# "auto" router) with a literal "-1" token price, which would otherwise
# overflow the column outright (observed in production: -1 -> -$1,000,000/Mtok).
_MAX_RATE = Decimal(1_000_000)


def lookup_rate(db: Session, model: str) -> tuple[Decimal, Decimal] | None:
    """Latest known (rate_in, rate_out) $/Mtok for `model`, or None if it has
    never been priced."""
    row = db.scalar(
        select(ModelPrice)
        .where(ModelPrice.model == model)
        # id as a tiebreaker: effective_from's DB-clock resolution (e.g.
        # SQLite's CURRENT_TIMESTAMP is whole seconds) can tie two rows
        # inserted moments apart - id, monotonic with insertion order, is
        # the only way to reliably pick the newer one.
        .order_by(ModelPrice.effective_from.desc(), ModelPrice.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    return row.rate_in_usd_per_mtok, row.rate_out_usd_per_mtok


@dataclass(frozen=True)
class RefreshResult:
    updated: int


def _tracked_models() -> set[str]:
    """The only models this project ever calls (AD-3's two independent
    adapters). OpenRouter lists hundreds of models this project has no use
    for; there is no reason to keep a price on file for any of them."""
    return {m for m in (settings.external_llm_model, settings.local_llm_model) if m}


def refresh_from_openrouter(db: Session) -> RefreshResult:
    """Fetches OpenRouter's public model list and inserts a new `model_prices`
    row for each *tracked* model (`_tracked_models`) whose rate actually
    changed - existing rows are never updated or deleted (AD-21), so calls
    already written keep the rate that was in effect when they ran.

    Raises on any transport/HTTP/JSON failure - it does not catch, so the
    caller (cli.py's `refresh-pricing`) can tell "source unavailable" (exit 2,
    per the infra contract) apart from a real DB failure (exit 1).
    """
    tracked_models = _tracked_models()
    if not tracked_models:
        return RefreshResult(updated=0)

    url = f"{settings.external_llm_base_url.rstrip('/')}/models"
    response = httpx.get(url, timeout=_FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    body = response.json()

    updated = 0
    for entry in body.get("data", []):
        model = entry.get("id")
        if model not in tracked_models:
            continue
        pricing = entry.get("pricing")
        if not isinstance(pricing, dict):
            continue
        try:
            rate_in = (Decimal(str(pricing["prompt"])) * _USD_PER_TOKEN_TO_USD_PER_MTOK).quantize(
                _RATE_QUANTUM
            )
            rate_out = (
                Decimal(str(pricing["completion"])) * _USD_PER_TOKEN_TO_USD_PER_MTOK
            ).quantize(_RATE_QUANTUM)
        except (KeyError, TypeError, ArithmeticError):
            continue
        if not (0 <= rate_in < _MAX_RATE and 0 <= rate_out < _MAX_RATE):
            continue

        if lookup_rate(db, model) == (rate_in, rate_out):
            continue

        db.add(
            ModelPrice(
                model=model,
                rate_in_usd_per_mtok=rate_in,
                rate_out_usd_per_mtok=rate_out,
                source="api",
            )
        )
        updated += 1
    db.commit()
    return RefreshResult(updated=updated)
