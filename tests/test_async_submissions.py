from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.execution.judge import JudgeReport
from app.models.enums import SubmissionStatus, Verdict
from app.models.submission import Submission
from app.services.submissions import judge_queued_submission
from tests.conftest import (
    API,
    SOLUTION_ACCEPTED,
    SOLUTION_RUNTIME_ERROR,
    SOLUTION_WRONG,
)


def _submit(client, headers, problem_id, source=SOLUTION_ACCEPTED):
    return client.post(
        f"{API}/submissions",
        headers=headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": source,
        },
    )


def _load_submission(submission_id: int) -> Submission:
    with SessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        return submission


def test_submission_is_enqueued(client, user_headers, problem_id, monkeypatch):
    enqueued: list[int] = []
    monkeypatch.setattr(
        "app.routes.submissions.enqueue_submission_judging", enqueued.append
    )

    response = _submit(client, user_headers, problem_id)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == SubmissionStatus.QUEUED.value
    assert body["verdict"] == Verdict.PENDING.value
    assert enqueued == [body["id"]]


def test_worker_changes_queued_to_running_to_completed(
    client, user_headers, problem_id, monkeypatch
):
    response = _submit(client, user_headers, problem_id)
    submission_id = response.json()["id"]
    observed_statuses: list[str] = []

    def fake_judge_submission(**kwargs):
        observed_statuses.append(_load_submission(submission_id).status)
        return JudgeReport(
            verdict=Verdict.ACCEPTED.value,
            score=100,
            passed_tests=3,
            total_tests=3,
            execution_time_ms=12.5,
            memory_kb=2048,
            backend="test",
        )

    monkeypatch.setattr(
        "app.services.submissions.judge_submission", fake_judge_submission
    )

    assert judge_queued_submission(submission_id) is True

    submission = _load_submission(submission_id)
    assert observed_statuses == [SubmissionStatus.RUNNING.value]
    assert submission.status == SubmissionStatus.COMPLETED.value
    assert submission.verdict == Verdict.ACCEPTED.value


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SOLUTION_ACCEPTED, Verdict.ACCEPTED.value),
        (SOLUTION_WRONG, Verdict.WRONG_ANSWER.value),
        (SOLUTION_RUNTIME_ERROR, Verdict.RUNTIME_ERROR.value),
    ],
)
def test_worker_stores_verdicts(client, user_headers, problem_id, source, expected):
    response = _submit(client, user_headers, problem_id, source)
    submission_id = response.json()["id"]

    assert judge_queued_submission(submission_id) is True

    submission = _load_submission(submission_id)
    assert submission.status == SubmissionStatus.COMPLETED.value
    assert submission.verdict == expected


def test_infrastructure_failure_marks_submission_failed(
    client, user_headers, problem_id, monkeypatch
):
    response = _submit(client, user_headers, problem_id)
    submission_id = response.json()["id"]

    def explode(**kwargs):
        raise RuntimeError("database password leaked in stack trace")

    monkeypatch.setattr("app.services.submissions.judge_submission", explode)

    assert judge_queued_submission(submission_id) is True

    submission = _load_submission(submission_id)
    assert submission.status == SubmissionStatus.FAILED.value
    assert submission.verdict == Verdict.INTERNAL_ERROR.value
    assert submission.error_message == "The judge encountered an internal error"


def test_worker_does_not_execute_completed_submission(
    client, user_headers, problem_id, monkeypatch
):
    response = _submit(client, user_headers, problem_id)
    submission_id = response.json()["id"]
    judge_queued_submission(submission_id)

    def fail_if_called(**kwargs):
        raise AssertionError("completed submissions must not be re-executed")

    monkeypatch.setattr("app.services.submissions.judge_submission", fail_if_called)

    assert judge_queued_submission(submission_id) is False


def test_user_code_verdict_is_not_retried(client, user_headers, problem_id):
    response = _submit(client, user_headers, problem_id, SOLUTION_RUNTIME_ERROR)
    submission_id = response.json()["id"]

    assert judge_queued_submission(submission_id) is True
    assert judge_queued_submission(submission_id) is False

    submission = _load_submission(submission_id)
    assert submission.status == SubmissionStatus.COMPLETED.value
    assert submission.verdict == Verdict.RUNTIME_ERROR.value


def test_queue_failure_marks_submission_failed(client, user_headers, problem_id, monkeypatch):
    def unavailable(submission_id: int) -> None:
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(
        "app.routes.submissions.enqueue_submission_judging", unavailable
    )

    response = _submit(client, user_headers, problem_id)

    assert response.status_code == 503, response.text
    submission_id = response.json()["detail"]["submission_id"]
    submission = _load_submission(submission_id)
    assert submission.status == SubmissionStatus.FAILED.value
    assert submission.verdict == Verdict.INTERNAL_ERROR.value
