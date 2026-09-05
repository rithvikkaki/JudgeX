"""Contest standings.

The scoring rules, stated once:

* Only submissions **scoped to this contest** (``contest_id`` set) and made
  **inside the contest window** count.  Practice submissions never move a
  contest ranking.
* A problem is worth its ``ContestProblem.points`` value, awarded **once**, on
  the first accepted submission.  Re-submitting an already-solved problem adds
  nothing.
* Penalty is ICPC-style: for every solved problem, the minutes elapsed from
  contest start to the accepted submission, plus a fixed penalty per rejected
  attempt *made before* that solve.  Rejected attempts on problems that are
  never solved are free.
* Ranking is score descending, then penalty ascending, then username, so the
  order is total and stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.contest_problem import ContestProblem
from app.models.contest_registration import ContestRegistration
from app.models.enums import Verdict
from app.models.submission import Submission
from app.models.user import User
from app.schemas.leaderboard import (
    LeaderboardEntry,
    LeaderboardProblemCell,
    LeaderboardResponse,
)


@dataclass
class _ProblemProgress:
    attempts: int = 0
    solved_at: datetime | None = None
    wrong_before_solve: int = 0


@dataclass
class _UserProgress:
    user_id: int
    username: str
    per_problem: dict[int, _ProblemProgress] = field(default_factory=dict)


def build_leaderboard(db: Session, contest: Contest) -> LeaderboardResponse:
    contest_start = _as_aware(contest.start_time)
    contest_end = _as_aware(contest.end_time)

    links = list(
        db.scalars(
            select(ContestProblem)
            .where(ContestProblem.contest_id == contest.id)
            .order_by(ContestProblem.order_index, ContestProblem.id)
        )
    )
    points_by_problem = {link.problem_id: link.points for link in links}
    label_by_problem = {link.problem_id: link.label for link in links}

    participants = list(
        db.execute(
            select(User.id, User.username, ContestRegistration.registered_at)
            .join(ContestRegistration, ContestRegistration.user_id == User.id)
            .where(ContestRegistration.contest_id == contest.id)
        )
    )

    progress: dict[int, _UserProgress] = {
        row.id: _UserProgress(user_id=row.id, username=row.username)
        for row in participants
    }

    if links and progress:
        _accumulate(db, contest, contest_start, contest_end, points_by_problem, progress)

    entries = [
        _to_entry(user, points_by_problem, label_by_problem, contest, contest_start)
        for user in progress.values()
    ]

    entries.sort(key=lambda e: (-e.score, e.penalty, e.username.lower()))

    # Equal (score, penalty) shares a rank; the next distinct pair skips ahead,
    # which is how competitive standings normally read.
    previous_key: tuple[int, int] | None = None
    previous_rank = 0
    for position, entry in enumerate(entries, start=1):
        key = (entry.score, entry.penalty)
        if key == previous_key:
            entry.rank = previous_rank
        else:
            entry.rank = position
            previous_rank = position
            previous_key = key

    return LeaderboardResponse(
        contest_id=contest.id,
        contest_title=contest.title,
        state=contest.state.value,
        total_participants=len(entries),
        entries=entries,
    )


def _accumulate(
    db: Session,
    contest: Contest,
    contest_start: datetime,
    contest_end: datetime,
    points_by_problem: dict[int, int],
    progress: dict[int, _UserProgress],
) -> None:
    submissions = db.scalars(
        select(Submission)
        .where(
            Submission.contest_id == contest.id,
            Submission.problem_id.in_(points_by_problem.keys()),
            Submission.user_id.in_(progress.keys()),
        )
        .order_by(Submission.created_at, Submission.id)
    )

    for submission in submissions:
        created = _as_aware(submission.created_at)
        # Defence in depth: submissions are already window-checked on write,
        # but a contest's times can be edited afterwards.
        if created < contest_start or created > contest_end:
            continue

        user = progress.get(submission.user_id)
        if user is None:
            continue

        cell = user.per_problem.setdefault(submission.problem_id, _ProblemProgress())

        if cell.solved_at is not None:
            # Already solved: later submissions are ignored entirely, so a user
            # cannot farm points or penalty by resubmitting.
            continue

        cell.attempts += 1

        if submission.verdict == Verdict.ACCEPTED.value:
            cell.solved_at = created
        else:
            cell.wrong_before_solve += 1


def _to_entry(
    user: _UserProgress,
    points_by_problem: dict[int, int],
    label_by_problem: dict[int, str | None],
    contest: Contest,
    contest_start: datetime,
) -> LeaderboardEntry:
    score = 0
    penalty = 0
    solved = 0
    cells: list[LeaderboardProblemCell] = []

    for problem_id, points in points_by_problem.items():
        cell = user.per_problem.get(problem_id, _ProblemProgress())
        is_solved = cell.solved_at is not None
        minutes: int | None = None

        if is_solved:
            solved += 1
            score += points
            minutes = max(
                0, int((cell.solved_at - contest_start).total_seconds() // 60)
            )
            penalty += minutes
            penalty += cell.wrong_before_solve * contest.penalty_minutes_per_wrong

        cells.append(
            LeaderboardProblemCell(
                problem_id=problem_id,
                label=label_by_problem.get(problem_id),
                solved=is_solved,
                attempts=cell.attempts,
                points=points if is_solved else 0,
                solved_at_minutes=minutes,
            )
        )

    return LeaderboardEntry(
        rank=0,  # assigned by the caller after sorting
        user_id=user.user_id,
        username=user.username,
        solved=solved,
        score=score,
        penalty=penalty,
        problems=cells,
    )


def _as_aware(value: datetime) -> datetime:
    """SQLite loses tzinfo on round-trip; treat naive timestamps as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
