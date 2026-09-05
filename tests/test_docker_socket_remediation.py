import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.models.enums import Language

def test_run_code_delegates_to_execute_run_code_not_docker_direct(
    client: TestClient, user_headers: dict
):
    mock_response = {
        "outcome": "ok",
        "stdout": "15\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 12.5,
        "memory_kb": 1024,
        "compile_output": None,
        "backend": "local",
    }
    
    with patch("app.routes.submissions.execute_run_code", return_value=mock_response) as mock_exec, \
         patch("app.execution.judge.run_once") as mock_run_once:
        
        response = client.post(
            "/api/v1/submissions/run",
            headers=user_headers,
            json={
                "language": Language.PYTHON.value,
                "source_code": "print(10 + 5)",
                "stdin": "",
            },
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "ok"
    assert data["stdout"] == "15\n"
    
    # Assert API route delegated to execute_run_code (not Docker directly)
    mock_exec.assert_called_once()
    
    # Assert run_once was never called directly from the API route
    mock_run_once.assert_not_called()

def test_run_code_worker_timeout(client: TestClient, user_headers: dict):
    with patch("app.routes.submissions.execute_run_code", side_effect=TimeoutError("Worker timed out")):
        response = client.post(
            "/api/v1/submissions/run",
            headers=user_headers,
            json={
                "language": Language.PYTHON.value,
                "source_code": "import time; time.sleep(100)",
                "stdin": "",
            },
        )
    
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()

def test_run_code_worker_failure(client: TestClient, user_headers: dict):
    with patch("app.routes.submissions.execute_run_code", side_effect=Exception("Broker unreachable")):
        response = client.post(
            "/api/v1/submissions/run",
            headers=user_headers,
            json={
                "language": Language.PYTHON.value,
                "source_code": "print('hello')",
                "stdin": "",
            },
        )
    
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()

def test_run_code_requires_authentication(client: TestClient):
    response = client.post(
        "/api/v1/submissions/run",
        json={
            "language": Language.PYTHON.value,
            "source_code": "print('hello')",
            "stdin": "",
        },
    )
    assert response.status_code == 401
