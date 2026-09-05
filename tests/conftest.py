"""Shared pytest fixtures.

Every test runs against a throw-away SQLite database and the ``local``
execution backend, so the suite needs no Postgres and no Docker daemon.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# These must be set before `app.config` is imported for the first time.
_TMP_DB = Path(tempfile.gettempdir()) / "judge_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-outside-tests")
os.environ.setdefault("EXECUTION_BACKEND", "local")
os.environ.setdefault("ALLOW_UNSAFE_LOCAL_EXECUTION", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("ADMIN_EMAILS", "admin@example.com")
os.environ.setdefault("ENVIRONMENT", "development")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.submissions import judge_queued_submission  # noqa: E402

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fresh_database():
    """Drop and recreate every table around each test for full isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _disable_real_queue(monkeypatch):
    """API tests assert enqueue intent without needing Redis or Celery."""
    monkeypatch.setattr(
        "app.routes.submissions.enqueue_submission_judging",
        lambda submission_id: None,
    )

    def _mock_execute_run_code(
        source_code: str,
        language: str,
        stdin: str,
        time_limit_ms: int | None = None,
        memory_limit_mb: int | None = None,
    ) -> dict:
        from app.execution.judge import run_once

        result = run_once(
            source_code=source_code,
            language=language,
            stdin=stdin,
            time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
        )
        return {
            "outcome": result.outcome.value,
            "stdout": result.stdout,
            "stderr": result.stderr or result.detail,
            "exit_code": result.exit_code,
            "execution_time_ms": result.duration_ms,
            "memory_kb": result.memory_kb,
            "compile_output": result.compile_output or None,
            "backend": result.backend,
        }

    monkeypatch.setattr(
        "app.routes.submissions.execute_run_code",
        _mock_execute_run_code,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def judge_submission_record(submission_id: int) -> bool:
    return judge_queued_submission(submission_id)


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        f"{API}/auth/register",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "password": "adminPass123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def user_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        f"{API}/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "alicePass123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def problem_id(client: TestClient, admin_headers: dict[str, str]) -> int:
    """A published 'a + b' problem with one sample and two hidden cases."""
    response = client.post(
        f"{API}/problems",
        headers=admin_headers,
        json={
            "title": "Sum of Two Numbers",
            "description": "Read two integers and print their sum.",
            "difficulty": "Easy",
            "input_format": "Two space-separated integers",
            "output_format": "Their sum",
            "constraints": "-10^9 <= a, b <= 10^9",
            "sample_input": "2 3",
            "sample_output": "5",
        },
    )
    assert response.status_code == 201, response.text
    pid = response.json()["id"]

    client.post(
        f"{API}/testcases/problem/{pid}/bulk",
        headers=admin_headers,
        json={
            "test_cases": [
                {"input_data": "2 3", "expected_output": "5", "is_sample": True},
                {"input_data": "10 20", "expected_output": "30"},
                {"input_data": "-5 5", "expected_output": "0"},
            ]
        },
    )
    return pid


# Reference solutions used across the judging tests.
SOLUTION_ACCEPTED = "a, b = map(int, input().split())\nprint(a + b)\n"
SOLUTION_WRONG = "a, b = map(int, input().split())\nprint(a - b)\n"
SOLUTION_RUNTIME_ERROR = "raise ValueError('boom')\n"
SOLUTION_SYNTAX_ERROR = "def broken(:\n"
SOLUTION_INFINITE_LOOP = "while True:\n    pass\n"
