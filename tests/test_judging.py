"""Verdict generation - the core promise of the service."""

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.execution.judge import judge_submission, normalise_output
from app.models.problem import Problem
from app.models.test_case import TestCase as TCModel
from tests.conftest import (
    API,
    SOLUTION_ACCEPTED,
    SOLUTION_INFINITE_LOOP,
    SOLUTION_RUNTIME_ERROR,
    SOLUTION_SYNTAX_ERROR,
    SOLUTION_WRONG,
    judge_submission_record,
)


def submit(client, headers, problem_id, source, language="python", contest_id=None, judge=True):
    payload = {
        "problem_id": problem_id,
        "language": language,
        "source_code": source,
    }
    if contest_id is not None:
        payload["contest_id"] = contest_id
    response = client.post(f"{API}/submissions", headers=headers, json=payload)
    if judge and response.status_code == 202:
        judge_submission_record(response.json()["id"])
        return client.get(
            f"{API}/submissions/{response.json()['id']}", headers=headers
        )
    return response


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SOLUTION_ACCEPTED, "Accepted"),
        (SOLUTION_WRONG, "Wrong Answer"),
        (SOLUTION_RUNTIME_ERROR, "Runtime Error"),
        (SOLUTION_SYNTAX_ERROR, "Compilation Error"),
        (SOLUTION_INFINITE_LOOP, "Time Limit Exceeded"),
    ],
)
def test_each_verdict_is_produced(client, user_headers, problem_id, source, expected):
    response = submit(client, user_headers, problem_id, source)
    assert response.status_code == 200, response.text
    assert response.json()["verdict"] == expected


def test_post_submission_returns_queued_immediately(client, user_headers, problem_id):
    response = submit(
        client, user_headers, problem_id, SOLUTION_ACCEPTED, judge=False
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "Queued"
    assert body["verdict"] == "Pending"
    assert body["total_tests"] == 3


def test_accepted_submission_scores_full_marks(client, user_headers, problem_id):
    body = submit(client, user_headers, problem_id, SOLUTION_ACCEPTED).json()
    assert body["score"] == 100
    assert body["passed_tests"] == body["total_tests"] == 3
    assert body["failed_test_index"] is None
    assert body["execution_time_ms"] > 0


def test_wrong_answer_reports_partial_progress(client, user_headers, problem_id):
    body = submit(client, user_headers, problem_id, SOLUTION_WRONG).json()
    # The sample case runs first and fails immediately, so nothing passed.
    assert body["failed_test_index"] == 1
    assert body["score"] < 100


def test_hidden_test_data_never_leaves_the_server(client, user_headers, problem_id):
    report = _judge_directly(problem_id, SOLUTION_ACCEPTED)
    for result in report.test_results:
        if not result.is_sample:
            assert result.input_data is None
            assert result.expected_output is None
            assert result.actual_output is None
    # And the hidden expected values never appear anywhere in the payload.
    assert "30" not in str(report.test_results)


def test_sample_results_include_a_diff(client, user_headers, problem_id):
    report = _judge_directly(problem_id, SOLUTION_WRONG)
    sample = next(r for r in report.test_results if r.is_sample)
    assert sample.input_data == "2 3"
    assert sample.expected_output == "5"
    assert sample.actual_output == "-1"


def test_submitting_requires_authentication(client, problem_id):
    response = client.post(
        f"{API}/submissions",
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": SOLUTION_ACCEPTED,
        },
    )
    assert response.status_code == 401


def test_problem_without_test_cases_cannot_be_judged(
    client, admin_headers, user_headers
):
    created = client.post(
        f"{API}/problems",
        headers=admin_headers,
        json={
            "title": "Untested Problem",
            "description": "has no test cases at all",
            "difficulty": "Easy",
            "input_format": "-",
            "output_format": "-",
            "constraints": "-",
            "sample_input": "-",
            "sample_output": "-",
        },
    ).json()
    response = submit(client, user_headers, created["id"], SOLUTION_ACCEPTED)
    assert response.status_code == 409


def test_source_code_is_private_to_its_author(client, user_headers, problem_id):
    submission_id = submit(client, user_headers, problem_id, SOLUTION_ACCEPTED).json()["id"]

    other = client.post(
        f"{API}/auth/register",
        json={
            "username": "mallory",
            "email": "mallory@example.com",
            "password": "malloryPass1",
        },
    ).json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}

    assert client.get(f"{API}/submissions/{submission_id}", headers=headers).status_code == 403
    assert client.get(f"{API}/submissions/{submission_id}", headers=user_headers).status_code == 200


def test_run_endpoint_does_not_persist_a_submission(client, user_headers, problem_id):
    response = client.post(
        f"{API}/submissions/run",
        headers=user_headers,
        json={"language": "python", "source_code": "print(input())", "stdin": "ping"},
    )
    assert response.status_code == 200
    assert response.json()["stdout"].strip() == "ping"
    assert client.get(f"{API}/submissions", headers=user_headers).json()["total"] == 0


def test_submission_history_is_filterable(client, user_headers, problem_id):
    submit(client, user_headers, problem_id, SOLUTION_ACCEPTED)
    submit(client, user_headers, problem_id, SOLUTION_WRONG)

    assert client.get(f"{API}/submissions", headers=user_headers).json()["total"] == 2
    accepted = client.get(
        f"{API}/submissions", headers=user_headers, params={"verdict": "Accepted"}
    ).json()
    assert accepted["total"] == 1


class TestOutputNormalisation:
    """Whitespace conventions applied before comparing answers."""

    def test_trailing_newline_is_ignored(self):
        assert normalise_output("5\n") == normalise_output("5")

    def test_trailing_spaces_per_line_are_ignored(self):
        assert normalise_output("1 2  \n3 4") == normalise_output("1 2\n3 4")

    def test_windows_line_endings_are_normalised(self):
        assert normalise_output("a\r\nb") == normalise_output("a\nb")

    def test_internal_blank_lines_are_significant(self):
        assert normalise_output("a\n\nb") != normalise_output("a\nb")

    def test_leading_whitespace_is_significant(self):
        assert normalise_output("  a") != normalise_output("a")


def _judge_directly(problem_id: int, source: str):
    with SessionLocal() as db:
        problem = db.get(Problem, problem_id)
        assert problem is not None
        test_cases = list(
            db.scalars(
                select(TCModel).where(TCModel.problem_id == problem_id)
            )
        )
        return judge_submission(
            source_code=source,
            language="python",
            test_cases=test_cases,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
        )
