"""Contest ↔ problem mapping.

This module replaces the previous ``contest_problem.py``, which could not be
imported at all: it referenced ``router``, ``Depends``, ``HTTPException``,
``Session``, ``get_db`` and ``Contest`` without defining or importing any of
them, and was never registered on the application.
"""

from __future__ import annotations

from string import ascii_uppercase

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_admin, get_optional_user
from app.dependencies.database import get_db
from app.models.contest import Contest
from app.models.contest_problem import ContestProblem
from app.models.enums import ContestState
from app.models.problem import Problem
from app.models.user import User
from app.schemas.common import Message
from app.schemas.contest_problem import (
    ContestProblemCreate,
    ContestProblemDetail,
    ContestProblemResponse,
    ContestProblemUpdate,
)
from app.schemas.problem import ProblemSummary

router = APIRouter(prefix="/contests", tags=["Contest Problems"])


@router.get(
    "/{contest_id}/problems",
    response_model=list[ContestProblemDetail],
    summary="Problems in a contest",
)
def list_contest_problems(
    contest_id: int,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> list[ContestProblemDetail]:
    contest = _require_contest(db, contest_id)
    is_admin = bool(viewer and viewer.is_admin)

    # The problem set of an unstarted contest is withheld, otherwise anyone
    # could read the questions before the clock starts.
    if contest.state is ContestState.UPCOMING and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contest problems are revealed when the contest starts",
        )

    rows = db.execute(
        select(ContestProblem, Problem)
        .join(Problem, Problem.id == ContestProblem.problem_id)
        .where(ContestProblem.contest_id == contest_id)
        .order_by(ContestProblem.order_index, ContestProblem.id)
    ).all()

    return [
        ContestProblemDetail(
            id=link.id,
            contest_id=link.contest_id,
            problem_id=link.problem_id,
            label=link.label,
            points=link.points,
            order_index=link.order_index,
            problem=ProblemSummary.model_validate(problem),
        )
        for link, problem in rows
    ]


@router.post(
    "/{contest_id}/problems",
    response_model=ContestProblemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a problem to a contest (admin only)",
)
def add_contest_problem(
    contest_id: int,
    payload: ContestProblemCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ContestProblem:
    _require_contest(db, contest_id)

    if db.get(Problem, payload.problem_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    existing_count = int(
        db.scalar(
            select(func.count(ContestProblem.id)).where(
                ContestProblem.contest_id == contest_id
            )
        )
        or 0
    )

    link = ContestProblem(
        contest_id=contest_id,
        problem_id=payload.problem_id,
        points=payload.points,
        order_index=payload.order_index or existing_count,
        label=payload.label or _next_label(existing_count),
    )
    db.add(link)

    try:
        db.commit()
    except IntegrityError:
        # uq_contest_problem: the same problem cannot be added twice, even if
        # two admins race.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That problem is already in this contest",
        ) from None

    db.refresh(link)
    return link


@router.patch(
    "/{contest_id}/problems/{problem_id}",
    response_model=ContestProblemResponse,
    summary="Change a contest problem's label, points or order (admin only)",
)
def update_contest_problem(
    contest_id: int,
    problem_id: int,
    payload: ContestProblemUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ContestProblem:
    link = _require_link(db, contest_id, problem_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(link, field, value)

    db.commit()
    db.refresh(link)
    return link


@router.delete(
    "/{contest_id}/problems/{problem_id}",
    response_model=Message,
    summary="Remove a problem from a contest (admin only)",
)
def remove_contest_problem(
    contest_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Message:
    link = _require_link(db, contest_id, problem_id)
    db.delete(link)
    db.commit()
    return Message(message="Problem removed from contest")


# ---------------------------------------------------------------------- #
def _require_contest(db: Session, contest_id: int) -> Contest:
    contest = db.get(Contest, contest_id)
    if contest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )
    return contest


def _require_link(db: Session, contest_id: int, problem_id: int) -> ContestProblem:
    link = db.scalar(
        select(ContestProblem).where(
            ContestProblem.contest_id == contest_id,
            ContestProblem.problem_id == problem_id,
        )
    )
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That problem is not in this contest",
        )
    return link


def _next_label(index: int) -> str:
    """A, B, ... Z, AA, AB, ... for contests with more than 26 problems."""
    label = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = ascii_uppercase[remainder] + label
    return label
