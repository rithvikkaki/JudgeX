import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.models.enums import Language, SubmissionStatus
from app.models.submission import Submission

def test_async_judging_dispatches_task_and_not_sync(
    client: TestClient, user_headers: dict, problem_id: int
):
    db = SessionLocal()
    with patch("app.routes.submissions.enqueue_submission_judging") as mock_enqueue, \
         patch("app.execution.judge.judge_submission") as mock_sync_judge:
        response = client.post(
            "/api/v1/submissions",
            headers=user_headers,
            json={
                "problem_id": problem_id,
                "language": Language.PYTHON.value,
                "source_code": "print('hello')",
            },
        )
    
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == SubmissionStatus.QUEUED.value
    
    submission_id = data["id"]
    mock_enqueue.assert_called_once_with(submission_id)
    
    # Prove the synchronous judge_submission is not called by the API route
    mock_sync_judge.assert_not_called()
    
    submission = db.get(Submission, submission_id)
    assert submission.status == SubmissionStatus.QUEUED.value
    db.close()

def test_async_judging_handles_queue_failure(
    client: TestClient, user_headers: dict, problem_id: int
):
    db = SessionLocal()
    with patch("app.routes.submissions.enqueue_submission_judging", side_effect=Exception("Redis down")):
        response = client.post(
            "/api/v1/submissions",
            headers=user_headers,
            json={
                "problem_id": problem_id,
                "language": Language.PYTHON.value,
                "source_code": "print('hello')",
            },
        )
    
    assert response.status_code == 503
    data = response.json()
    assert "unavailable" in data["detail"]["message"].lower()
    
    submission_id = data["detail"]["submission_id"]
    submission = db.get(Submission, submission_id)
    assert submission.status == SubmissionStatus.FAILED.value
    db.close()

def test_worker_service_performs_actual_judging(
    problem_id: int
):
    db = SessionLocal()
    from app.services.submissions import create_queued_submission, judge_queued_submission
    from app.models.user import User
    
    user = db.query(User).first()
    
    submission = create_queued_submission(
        db,
        user_id=user.id,
        problem_id=problem_id,
        contest_id=None,
        language=Language.PYTHON.value,
        source_code="print('hello')",
        total_tests=1,
    )
    
    result = judge_queued_submission(submission.id)
    assert result is True
    
    db.refresh(submission)
    assert submission.status == SubmissionStatus.COMPLETED.value
    db.close()
    
def test_duplicate_task_execution_protected(
    problem_id: int
):
    db = SessionLocal()
    from app.services.submissions import create_queued_submission, judge_queued_submission
    from app.models.enums import SubmissionStatus
    from app.models.user import User
    
    user = db.query(User).first()
    
    submission = create_queued_submission(
        db,
        user_id=user.id,
        problem_id=problem_id,
        contest_id=None,
        language=Language.PYTHON.value,
        source_code="print('hello')",
        total_tests=1,
    )
    
    submission.status = SubmissionStatus.RUNNING.value
    db.commit()
    
    result = judge_queued_submission(submission.id)
    assert result is False
    db.close()

