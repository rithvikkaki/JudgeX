"""Targeted unit tests for Phase 1 security, CORS, LocalBackend safety policy, and rate limiting."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.execution.base import ExecutionRequest, Outcome
from app.execution.local_backend import LocalBackend
from app.main import app


class TestCORSSafety:
    def test_wildcard_origin_disables_credentials(self):
        s = Settings(CORS_ORIGINS="*")
        assert s.cors_origin_list == ["*"]
        assert s.cors_allow_credentials is False

    def test_explicit_origins_enable_credentials(self):
        s = Settings(CORS_ORIGINS="http://localhost:5173, http://localhost:3000")
        assert s.cors_origin_list == ["http://localhost:5173", "http://localhost:3000"]
        assert s.cors_allow_credentials is True


class TestUnsafeLocalExecutionPolicy:
    def test_local_execution_rejected_when_flag_is_false(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "ALLOW_UNSAFE_LOCAL_EXECUTION", False)
        backend = LocalBackend()

        result = backend.run(
            ExecutionRequest(language="python", source_code="print('hello')")
        )
        assert result.outcome is Outcome.INTERNAL_ERROR
        assert "Secure code execution infrastructure is unavailable" in result.detail
        assert backend.describe()["available"] is False

    def test_local_execution_allowed_when_flag_is_true(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "ALLOW_UNSAFE_LOCAL_EXECUTION", True)
        backend = LocalBackend()

        result = backend.run(
            ExecutionRequest(language="python", source_code="print('hello')")
        )
        assert result.outcome is Outcome.OK
        assert result.stdout.strip() == "hello"
        assert backend.describe()["available"] is True


class TestRateLimiting:
    def test_rate_limit_triggers_429(self, monkeypatch):
        from app.config import settings

        # Enable rate limiting on limiter instance and lower threshold for test
        monkeypatch.setattr(app.state.limiter, "enabled", True)
        monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
        monkeypatch.setattr(settings, "RATE_LIMIT_AUTH", "2/minute")

        # Reset limiter storage state for clean test isolation
        app.state.limiter.reset()

        try:
            client = TestClient(app)

            # First 2 login requests should return normal response (401 invalid creds)
            r1 = client.post("/api/v1/auth/login", json={"email": "u1@test.com", "password": "p"})
            assert r1.status_code == 401, r1.text

            r2 = client.post("/api/v1/auth/login", json={"email": "u2@test.com", "password": "p"})
            assert r2.status_code == 401, r2.text

            # 3rd request exceeds limit (2/min) and returns 429
            r3 = client.post("/api/v1/auth/login", json={"email": "u3@test.com", "password": "p"})
            assert r3.status_code == 429, r3.text
        finally:
            monkeypatch.setattr(app.state.limiter, "enabled", False)
            app.state.limiter.reset()
