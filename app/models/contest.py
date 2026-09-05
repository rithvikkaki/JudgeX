from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ContestState

if TYPE_CHECKING:
    from app.models.contest_problem import ContestProblem
    from app.models.contest_registration import ContestRegistration
    from app.models.submission import Submission


class Contest(TimestampMixin, Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(280), unique=True, index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )

    # Penalty added per rejected attempt on a problem that is later solved.
    penalty_minutes_per_wrong: Mapped[int] = mapped_column(
        Integer, default=20, server_default="20", nullable=False
    )

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    problem_links: Mapped[list["ContestProblem"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ContestProblem.order_index",
    )

    registrations: Mapped[list["ContestRegistration"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    submissions: Mapped[list["Submission"]] = relationship(back_populates="contest")

    # ------------------------------------------------------------------ #
    # Derived properties
    # ------------------------------------------------------------------ #
    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() // 60)

    def state_at(self, moment: datetime | None = None) -> ContestState:
        now = moment or datetime.now(timezone.utc)
        start, end = _as_aware(self.start_time), _as_aware(self.end_time)
        if now < start:
            return ContestState.UPCOMING
        if now > end:
            return ContestState.ENDED
        return ContestState.RUNNING

    @property
    def state(self) -> ContestState:
        return self.state_at()

    @property
    def is_running(self) -> bool:
        return self.state is ContestState.RUNNING

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Contest id={self.id} title={self.title!r}>"


def _as_aware(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat naive values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
