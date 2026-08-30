from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base


class ModelPrice(Base):
    """One row per known $/Mtok rate for a model, append-only (ARCHITECTURE-SPINE
    AD-16, AD-21). A price change never updates or deletes an existing row -
    `refresh-pricing` only inserts a new one with a later `effective_from`.
    `lookup_rate` (telemetry/pricing.py) reads the newest row with
    `effective_from <= now` for a model; `outbound_calls` copies that rate
    onto itself at write time rather than holding a FK here, so a later
    refresh can never change a historical call's recorded cost.

    `source` is `"api"` (from `refresh-pricing`'s provider fetch) or
    `"manual"` (a human-entered correction) - not modeled as an enum, same
    convention as `outbound_calls.status`.
    """

    __tablename__ = "model_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String, index=True)
    rate_in_usd_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    rate_out_usd_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    effective_from: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source: Mapped[str] = mapped_column(String)
