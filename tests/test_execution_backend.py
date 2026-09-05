"""Contract tests for the sandbox backends.

The load-bearing invariant: **a backend never raises.** The judge turns an
``ExecutionResult`` into a verdict, so a raised exception becomes a 500 and the
user loses their submission entirely.

This was not hypothetical. The local backend called ``os.setsid()`` inside
``preexec_fn`` while also passing ``start_new_session=True``. CPython runs
``setsid()`` *before* ``preexec_fn``, so the second call failed with EPERM, and
CPython reports any ``preexec_fn`` failure as ``SubprocessError`` - which is not
an ``OSError``, so it slipped past a narrow handler. Every submission 500'd on
Linux while passing on Windows, which never runs ``preexec_fn`` at all.
"""

from app.execution.base import ExecutionRequest, Outcome
from app.execution.docker_backend import DockerBackend
from app.execution.local_backend import LocalBackend


class TestBackendNeverRaises:
    def test_unknown_language_is_reported_not_raised(self):
        result = LocalBackend().run(
            ExecutionRequest(language="brainfuck", source_code="+++")
        )
        assert result.outcome is Outcome.INTERNAL_ERROR
        assert "brainfuck" in result.detail

    def test_absurd_limits_do_not_raise(self):
        result = LocalBackend().run(
            ExecutionRequest(
                language="python",
                source_code="print(1)",
                time_limit_ms=1,
                memory_limit_mb=16,
                max_output_bytes=1024,
            )
        )
        assert isinstance(result.outcome, Outcome)

    def test_empty_source_does_not_raise(self):
        result = LocalBackend().run(
            ExecutionRequest(language="python", source_code="")
        )
        assert isinstance(result.outcome, Outcome)

    def test_docker_backend_reports_absence_instead_of_raising(self):
        # No daemon in CI; the backend must degrade rather than explode.
        result = DockerBackend().run(
            ExecutionRequest(language="python", source_code="print(1)")
        )
        assert isinstance(result.outcome, Outcome)
        if not DockerBackend().is_available():
            assert result.outcome is Outcome.INTERNAL_ERROR


class TestLocalBackendBehaviour:
    def test_successful_run_captures_stdout(self):
        result = LocalBackend().run(
            ExecutionRequest(
                language="python", source_code="print(input().upper())", stdin="hello"
            )
        )
        assert result.outcome is Outcome.OK
        assert result.stdout.strip() == "HELLO"

    def test_stdout_and_stderr_are_kept_separate(self):
        # Merging them makes a program that logs to stderr fail with a
        # spurious Wrong Answer.
        result = LocalBackend().run(
            ExecutionRequest(
                language="python",
                source_code=(
                    "import sys\n"
                    "print('answer')\n"
                    "print('debug noise', file=sys.stderr)\n"
                ),
            )
        )
        assert result.outcome is Outcome.OK
        assert result.stdout.strip() == "answer"
        assert "debug noise" not in result.stdout

    def test_nonzero_exit_is_a_runtime_error(self):
        result = LocalBackend().run(
            ExecutionRequest(language="python", source_code="raise SystemExit(3)")
        )
        assert result.outcome is Outcome.RUNTIME_ERROR
        assert result.exit_code == 3

    def test_infinite_loop_times_out(self):
        result = LocalBackend().run(
            ExecutionRequest(
                language="python", source_code="while True: pass", time_limit_ms=500
            )
        )
        assert result.outcome is Outcome.TIMEOUT

    def test_runaway_output_is_capped(self):
        result = LocalBackend().run(
            ExecutionRequest(
                language="python",
                source_code="print('x' * 1000000)",
                max_output_bytes=2048,
            )
        )
        assert result.outcome is Outcome.OUTPUT_EXCEEDED

    def test_child_environment_excludes_secrets(self):
        # The deployed demo shares an OS user between the API and submitted
        # code, so the child environment must not carry the app's secrets.
        result = LocalBackend().run(
            ExecutionRequest(
                language="python",
                source_code=(
                    "import os\n"
                    "print('DATABASE_URL' in os.environ, 'SECRET_KEY' in os.environ)\n"
                ),
            )
        )
        assert result.outcome is Outcome.OK
        assert result.stdout.strip() == "False False"
