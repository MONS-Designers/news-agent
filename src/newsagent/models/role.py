from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.field import Field


class Role(Base):
    """An admin-curated job function, scoped under exactly one Field.

    Names are unique per Field, not globally - "Researcher" legitimately exists
    under both Healthcare and Education.
    """

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("field_id", "name", name="uq_roles_field_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    field: Mapped["Field"] = relationship()
