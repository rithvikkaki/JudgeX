from __future__ import annotations

from app.celery_app import celery_app
from app.services.submissions import judge_queued_submission


if celery_app is not None:

    @celery_app.task(
        bind=True,
        name="app.tasks.submissions.judge_submission",
        autoretry_for=(),
        max_retries=0,
    )
    def judge_submission_task(self, submission_id: int) -> bool:
        return judge_queued_submission(submission_id)

    @celery_app.task(
        bind=True,
        name="app.tasks.submissions.run_code",
        autoretry_for=(),
        max_retries=0,
    )
    def run_code_task(
        self,
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

else:

    class _UnavailableTask:
        def delay(self, *args, **kwargs) -> None:
            raise RuntimeError("Celery is not installed")

        def apply_async(self, *args, **kwargs):
            raise RuntimeError("Celery is not installed")

    judge_submission_task = _UnavailableTask()
    run_code_task = _UnavailableTask()
