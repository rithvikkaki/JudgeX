"""Per-user analytics powering the dashboard.

Every figure is computed with a grouped SQL aggregate rather than by loading
submissions into Python, so the cost stays flat as a user's history grows.
"""

from __future__ import annotations

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.models.contest_registration import ContestRegistration
from app.models.enums import Verdict
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.schemas.dashboard import (
    DashboardResponse,
    DifficultyProgress,
    LanguageUsage,
    VerdictCount,
)
from app.schemas.submission import SubmissionSummary

RECENT_LIMIT = 10


def build_dashboard(db: Session, user: User) -> DashboardResponse:
    mine = Submission.user_id == user.id

    total = db.scalar(select(func.count(Submission.id)).where(mine)) or 0

    accepted = (
        db.scalar(
            select(func.count(Submission.id)).where(
                mine, Submission.verdict == Verdict.ACCEPTED.value
            )
        )
        or 0
    )

    problems_solved = (
        db.scalar(
            select(func.count(distinct(Submission.problem_id))).where(
                mine, Submission.verdict == Verdict.ACCEPTED.value
            )
        )
        or 0
    )

    problems_attempted = (
        db.scalar(select(func.count(distinct(Submission.problem_id))).where(mine)) or 0
    )

    contests_participated = (
        db.scalar(
            select(func.count(ContestRegistration.id)).where(
                ContestRegistration.user_id == user.id
            )
        )
        or 0
    )

    verdict_rows = db.execute(
        select(Submission.verdict, func.count(Submission.id))
        .where(mine)
        .group_by(Submission.verdict)
        .order_by(func.count(Submission.id).desc())
    ).all()

    language_rows = db.execute(
        select(
            Submission.language,
            func.count(Submission.id),
            func.sum(
                case((Submission.verdict == Verdict.ACCEPTED.value, 1), else_=0)
            ),
        )
        .where(mine)
        .group_by(Submission.language)
        .order_by(func.count(Submission.id).desc())
    ).all()

    # Solved-per-difficulty, against how many public problems exist at each.
    solved_by_difficulty = dict(
        db.execute(
            select(Problem.difficulty, func.count(distinct(Problem.id)))
            .join(Submission, Submission.problem_id == Problem.id)
            .where(mine, Submission.verdict == Verdict.ACCEPTED.value)
            .group_by(Problem.difficulty)
        ).all()
    )

    available_by_difficulty = dict(
        db.execute(
            select(Problem.difficulty, func.count(Problem.id))
            .where(Problem.is_public.is_(True))
            .group_by(Problem.difficulty)
        ).all()
    )

    recent = list(
        db.scalars(
            select(Submission)
            .where(mine)
            .order_by(Submission.created_at.desc(), Submission.id.desc())
            .limit(RECENT_LIMIT)
        )
    )

    return DashboardResponse(
        username=user.username,
        email=user.email,
        total_submissions=total,
        accepted_submissions=accepted,
        acceptance_rate=round(accepted * 100 / total, 2) if total else 0.0,
        problems_solved=problems_solved,
        problems_attempted=problems_attempted,
        contests_participated=contests_participated,
        best_contest_rank=None,
        verdict_breakdown=[
            VerdictCount(verdict=verdict, count=count) for verdict, count in verdict_rows
        ],
        difficulty_progress=[
            DifficultyProgress(
                difficulty=difficulty,
                solved=int(solved_by_difficulty.get(difficulty, 0)),
                total_available=int(count),
            )
            for difficulty, count in sorted(available_by_difficulty.items())
        ],
        language_usage=[
            LanguageUsage(
                language=language,
                submissions=int(count),
                accepted=int(accepted_count or 0),
            )
            for language, count, accepted_count in language_rows
        ],
        recent_submissions=[SubmissionSummary.model_validate(s) for s in recent],
    )
