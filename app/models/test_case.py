from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.problem import Problem


class TestCase(TimestampMixin, Base):
    """A single input/expected-output pair.

    ``is_sample`` cases are visible to every user; the rest are hidden and are
    only ever exposed to admins.  The judge runs samples first so that an
    obviously-wrong submission fails fast.
    """

    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), index=True, nullable=False
    )

    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)

    is_sample: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )

    # Controls execution order; samples are additionally sorted ahead of
    # hidden cases by the judge.
    order_index: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    problem: Mapped["Problem"] = relationship(back_populates="test_cases")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        kind = "sample" if self.is_sample else "hidden"
        return f"<TestCase id={self.id} problem={self.problem_id} {kind}>"
