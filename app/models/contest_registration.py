from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.contest import Contest
    from app.models.user import User


class ContestRegistration(Base):
    __tablename__ = "contest_registrations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    contest: Mapped["Contest"] = relationship(back_populates="registrations")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_registration"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ContestRegistration contest={self.contest_id} user={self.user_id}>"
