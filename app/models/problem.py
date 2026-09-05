from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.contest_problem import ContestProblem
    from app.models.submission import Submission
    from app.models.test_case import TestCase


class Problem(TimestampMixin, Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # URL-friendly identifier derived from the title on create.
    slug: Mapped[str] = mapped_column(
        String(280), unique=True, index=True, nullable=False
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)

    difficulty: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    input_format: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[str] = mapped_column(Text, nullable=False)
    sample_input: Mapped[str] = mapped_column(Text, nullable=False)
    sample_output: Mapped[str] = mapped_column(Text, nullable=False)

    # Per-problem resource ceilings handed to the sandbox at judge time.
    time_limit_ms: Mapped[int] = mapped_column(
        Integer, default=2000, server_default="2000", nullable=False
    )
    memory_limit_mb: Mapped[int] = mapped_column(
        Integer, default=128, server_default="128", nullable=False
    )

    is_public: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TestCase.order_index",
    )

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    contest_links: Mapped[list["ContestProblem"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Problem id={self.id} title={self.title!r}>"
