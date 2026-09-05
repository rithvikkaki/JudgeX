from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.contest import Contest
    from app.models.problem import Problem


class ContestProblem(TimestampMixin, Base):
    """Join row placing a problem inside a contest, with its point value."""

    __tablename__ = "contest_problems"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id", ondelete="CASCADE"), index=True, nullable=False
    )

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Display label within the contest ("A", "B", "C", ...).
    label: Mapped[str | None] = mapped_column(String(8), nullable=True)

    order_index: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    points: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", nullable=False
    )

    contest: Mapped["Contest"] = relationship(back_populates="problem_links")
    problem: Mapped["Problem"] = relationship(back_populates="contest_links")

    __table_args__ = (
        # Enforced by the database, so concurrent "add problem" calls cannot
        # both slip past the application-level existence check.
        UniqueConstraint("contest_id", "problem_id", name="uq_contest_problem"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ContestProblem contest={self.contest_id} problem={self.problem_id}>"
