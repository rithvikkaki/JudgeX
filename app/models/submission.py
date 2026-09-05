from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SubmissionStatus, Verdict

if TYPE_CHECKING:
    from app.models.contest import Contest
    from app.models.problem import Problem
    from app.models.user import User


class Submission(TimestampMixin, Base):
    """One judged attempt at a problem.

    ``contest_id`` is set when the submission was made inside a live contest
    window; the leaderboard scores only those rows, which is what keeps contest
    standings independent of practice submissions.
    """

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), index=True, nullable=False
    )

    contest_id: Mapped[int | None] = mapped_column(
        ForeignKey("contests.id", ondelete="SET NULL"), index=True, nullable=True
    )

    language: Mapped[str] = mapped_column(String(20), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default=SubmissionStatus.QUEUED.value, nullable=False
    )

    verdict: Mapped[str] = mapped_column(
        String(30), default=Verdict.PENDING.value, index=True, nullable=False
    )

    # Real measurements, not formatted strings: the API layer decides how to
    # render them and clients can sort/filter numerically.
    execution_time_ms: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False
    )
    memory_kb: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    passed_tests: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    total_tests: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # 0-100, proportional to the fraction of test cases passed.
    score: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # Compiler diagnostics or the runtime traceback, truncated. Never contains
    # hidden test-case data.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Index of the first failing test case (1-based), or NULL when accepted.
    failed_test_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="submissions")
    problem: Mapped["Problem"] = relationship(back_populates="submissions")
    contest: Mapped["Contest | None"] = relationship(back_populates="submissions")

    __table_args__ = (
        # Backs "my submissions, newest first" and the dashboard aggregates.
        Index("ix_submissions_user_created", "user_id", "created_at"),
        # Backs contest leaderboard scans.
        Index("ix_submissions_contest_user", "contest_id", "user_id"),
        # Backs "best result per user per problem".
        Index("ix_submissions_problem_user", "problem_id", "user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Submission id={self.id} verdict={self.verdict!r}>"
