from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.execution.languages import supported_languages
from app.limiter import limiter
from app.models.contest import Contest
from app.models.contest_problem import ContestProblem
from app.models.contest_registration import ContestRegistration
from app.models.enums import Language, Verdict
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.schemas.common import Page
from app.schemas.submission import (
    RunRequest,
    RunResponse,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionResponse,
    SubmissionSummary,
)
from app.services.submissions import (
    count_problem_test_cases,
    create_queued_submission,
    enqueue_submission_judging,
    execute_run_code,
    mark_submission_queue_failed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.get("/languages", summary="Languages the judge can execute")
def list_languages() -> list[dict]:
    return supported_languages()


@router.post(
    "",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a solution for asynchronous judging",
)
@limiter.limit(lambda: settings.RATE_LIMIT_SUBMIT)
def create_submission(
    request: Request,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmissionDetail:
    problem = db.get(Problem, payload.problem_id)
    if problem is None or (not problem.is_public and not user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )

    if payload.contest_id is not None:
        _validate_contest_submission(db, user, payload.contest_id, problem.id)

    total_tests = count_problem_test_cases(db, problem.id)
    if total_tests == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This problem has no test cases yet and cannot be judged",
        )

    submission = create_queued_submission(
        db,
        user_id=user.id,
        problem_id=problem.id,
        contest_id=payload.contest_id,
        language=payload.language.value,
        source_code=payload.source_code,
        total_tests=total_tests,
    )

    try:
        enqueue_submission_judging(submission.id)
    except Exception:  # noqa: BLE001 - queue failures must be visible
        logger.exception("Failed to enqueue submission %s", submission.id)
        mark_submission_queue_failed(
            db, submission, "The judge queue is temporarily unavailable"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "The judge queue is temporarily unavailable",
                "submission_id": submission.id,
            },
        ) from None

    return submission


@router.post(
    "/run",
    response_model=RunResponse,
    summary="Run code against custom input without recording a submission",
)
@limiter.limit(lambda: settings.RATE_LIMIT_RUN)
def run_code(
    request: Request,
    payload: RunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RunResponse:
    time_limit_ms = memory_limit_mb = None

    if payload.problem_id is not None:
        problem = db.get(Problem, payload.problem_id)
        if problem is not None:
            time_limit_ms = problem.time_limit_ms
            memory_limit_mb = problem.memory_limit_mb

    try:
        data = execute_run_code(
            source_code=payload.source_code,
            language=payload.language.value,
            stdin=payload.stdin,
            time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
        )
        return RunResponse(**data)
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Execution timed out waiting for worker",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The run service is temporarily unavailable",
        ) from None


@router.get(
    "",
    response_model=Page[SubmissionSummary],
    summary="Your submission history",
)
def my_submissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    problem_id: int | None = None,
    contest_id: int | None = None,
    verdict: Verdict | None = None,
    language: Language | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[SubmissionSummary]:
    conditions = [Submission.user_id == user.id]
    if problem_id is not None:
        conditions.append(Submission.problem_id == problem_id)
    if contest_id is not None:
        conditions.append(Submission.contest_id == contest_id)
    if verdict is not None:
        conditions.append(Submission.verdict == verdict.value)
    if language is not None:
        conditions.append(Submission.language == language.value)

    total = db.scalar(select(func.count(Submission.id)).where(*conditions)) or 0

    rows = list(
        db.scalars(
            select(Submission)
            .where(*conditions)
            .order_by(Submission.created_at.desc(), Submission.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )

    return Page[SubmissionSummary](
        items=[SubmissionSummary.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/problem/{problem_id}",
    response_model=list[SubmissionSummary],
    summary="Every accepted solution for a problem (source code withheld)",
)
def problem_submissions(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[SubmissionSummary]:
    rows = db.scalars(
        select(Submission)
        .where(
            Submission.problem_id == problem_id,
            Submission.verdict == Verdict.ACCEPTED.value,
        )
        .order_by(Submission.execution_time_ms.asc())
        .limit(limit)
    )
    return [SubmissionSummary.model_validate(row) for row in rows]


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="One submission, including its source code",
)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Submission:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )

    # Source code is private: only its author or an admin may read it.
    if submission.user_id != user.id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only view your own submissions",
        )

    return submission


# ---------------------------------------------------------------------- #
def _validate_contest_submission(
    db: Session, user: User, contest_id: int, problem_id: int
) -> None:
    """A contest-scoped submission must be legitimate on three counts."""
    contest = db.get(Contest, contest_id)
    if contest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    registered = db.scalar(
        select(ContestRegistration.id).where(
            ContestRegistration.contest_id == contest_id,
            ContestRegistration.user_id == user.id,
        )
    )
    if registered is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must join this contest before submitting to it",
        )

    now = datetime.now(timezone.utc)
    if not contest.is_running:
        detail = (
            "This contest has not started yet"
            if now < _aware(contest.start_time)
            else "This contest has ended"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    in_contest = db.scalar(
        select(ContestProblem.id).where(
            ContestProblem.contest_id == contest_id,
            ContestProblem.problem_id == problem_id,
        )
    )
    if in_contest is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This problem is not part of that contest",
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
