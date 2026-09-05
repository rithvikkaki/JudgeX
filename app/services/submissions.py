from __future__ import annotations

import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.execution.judge import MAX_ERROR_CHARS, judge_submission
from app.models.enums import SubmissionStatus, Verdict
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)

SAFE_INTERNAL_ERROR = "The judge encountered an internal error"


def count_problem_test_cases(db: Session, problem_id: int) -> int:
    return (
        db.scalar(select(func.count(TestCase.id)).where(TestCase.problem_id == problem_id))
        or 0
    )


def create_queued_submission(
    db: Session,
    *,
    user_id: int,
    problem_id: int,
    contest_id: int | None,
    language: str,
    source_code: str,
    total_tests: int,
) -> Submission:
    submission = Submission(
        user_id=user_id,
        problem_id=problem_id,
        contest_id=contest_id,
        language=language,
        source_code=source_code,
        status=SubmissionStatus.QUEUED.value,
        verdict=Verdict.PENDING.value,
        total_tests=total_tests,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def enqueue_submission_judging(submission_id: int) -> None:
    from app.tasks.submissions import judge_submission_task

    judge_submission_task.delay(submission_id)


def mark_submission_queue_failed(
    db: Session, submission: Submission, message: str = SAFE_INTERNAL_ERROR
) -> Submission:
    submission.status = SubmissionStatus.FAILED.value
    submission.verdict = Verdict.INTERNAL_ERROR.value
    submission.error_message = message[:MAX_ERROR_CHARS]
    db.commit()
    db.refresh(submission)
    return submission


def judge_queued_submission(submission_id: int) -> bool:
    """Judge one queued submission.

    Returns ``True`` when this call claimed and evaluated the submission.
    Returns ``False`` when the row no longer exists or is not queued, which is
    the idempotency guard for duplicate queue deliveries.
    """
    db = SessionLocal()
    try:
        claimed = _claim_submission(db, submission_id)
        if not claimed:
            return False

        submission = db.get(Submission, submission_id)
        if submission is None:
            return False

        problem = db.get(Problem, submission.problem_id)
        test_cases = list(
            db.scalars(select(TestCase).where(TestCase.problem_id == submission.problem_id))
        )
        if problem is None or not test_cases:
            _store_failed_result(
                db,
                submission_id,
                "Problem or test cases are no longer available",
            )
            return True

        try:
            report = judge_submission(
                source_code=submission.source_code,
                language=submission.language,
                test_cases=test_cases,
                time_limit_ms=problem.time_limit_ms,
                memory_limit_mb=problem.memory_limit_mb,
            )
        except Exception:  # noqa: BLE001 - preserve the submission row
            logger.exception("Judging failed for submission %s", submission_id)
            _store_failed_result(db, submission_id, SAFE_INTERNAL_ERROR)
            return True

        submission.status = SubmissionStatus.COMPLETED.value
        submission.verdict = report.verdict
        submission.score = report.score
        submission.passed_tests = report.passed_tests
        submission.total_tests = report.total_tests
        submission.execution_time_ms = report.execution_time_ms
        submission.memory_kb = report.memory_kb
        submission.error_message = report.error_message
        submission.failed_test_index = report.failed_test_index
        db.commit()
        return True
    finally:
        db.close()


def _claim_submission(db: Session, submission_id: int) -> bool:
    result = db.execute(
        update(Submission)
        .where(
            Submission.id == submission_id,
            Submission.status == SubmissionStatus.QUEUED.value,
        )
        .values(status=SubmissionStatus.RUNNING.value)
    )
    db.commit()
    return result.rowcount == 1


def _store_failed_result(db: Session, submission_id: int, message: str) -> None:
    db.execute(
        update(Submission)
        .where(Submission.id == submission_id)
        .values(
            status=SubmissionStatus.FAILED.value,
            verdict=Verdict.INTERNAL_ERROR.value,
            error_message=message[:MAX_ERROR_CHARS],
        )
    )
    db.commit()

def execute_run_code(
    *,
    source_code: str,
    language: str,
    stdin: str,
    time_limit_ms: int | None = None,
    memory_limit_mb: int | None = None,
) -> dict:
    from app.tasks.submissions import run_code_task

    try:
        task = run_code_task.apply_async(
            kwargs={
                "source_code": source_code,
                "language": language,
                "stdin": stdin,
                "time_limit_ms": time_limit_ms,
                "memory_limit_mb": memory_limit_mb,
            }
        )
        return task.get(timeout=30)
    except Exception as exc:
        logger.exception("Failed to execute run task on worker")
        raise exc
