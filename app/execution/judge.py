"""The evaluation pipeline.

Runs a submission against every test case for its problem and reduces the per
test results to a single verdict, a score, and time/memory metrics.

Ordering matters: **sample cases run first**, so a submission that fails an
example fails within one execution instead of burning the whole hidden suite.
Evaluation stops at the first non-accepted case, which is standard judge
behaviour and bounds worst-case cost to one run per submission.

Nothing derived from a *hidden* test case ever reaches the returned payload -
only its 1-based index.  Sample cases may expose their diff, because the user
could already see that data on the problem page.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.config import settings
from app.execution.base import ExecutionRequest, ExecutionResult, Outcome
from app.execution.engine import get_backend
from app.models.enums import Verdict
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)

#: Compiler/runtime diagnostics stored on the submission are clipped to this.
MAX_ERROR_CHARS = 4000

_OUTCOME_TO_VERDICT: dict[Outcome, Verdict] = {
    Outcome.TIMEOUT: Verdict.TIME_LIMIT_EXCEEDED,
    Outcome.MEMORY_EXCEEDED: Verdict.MEMORY_LIMIT_EXCEEDED,
    Outcome.OUTPUT_EXCEEDED: Verdict.OUTPUT_LIMIT_EXCEEDED,
    Outcome.RUNTIME_ERROR: Verdict.RUNTIME_ERROR,
    Outcome.COMPILE_ERROR: Verdict.COMPILATION_ERROR,
    Outcome.INTERNAL_ERROR: Verdict.INTERNAL_ERROR,
}


@dataclass(slots=True)
class TestCaseReport:
    """Per-test outcome. Hidden cases carry indices and metrics only."""

    index: int
    is_sample: bool
    passed: bool
    verdict: str
    execution_time_ms: float
    memory_kb: int
    # Populated for sample cases only.
    input_data: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None
    stderr: str | None = None


@dataclass(slots=True)
class JudgeReport:
    verdict: str
    score: int
    passed_tests: int
    total_tests: int
    execution_time_ms: float
    memory_kb: int
    backend: str
    error_message: str | None = None
    failed_test_index: int | None = None
    test_results: list[TestCaseReport] = field(default_factory=list)


def normalise_output(text: str) -> str:
    """Canonical form used for answer comparison.

    Trailing whitespace on each line and trailing blank lines are ignored -
    the near-universal convention for competitive judges, and it stops a
    stray newline from failing an otherwise correct solution.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    trimmed = [line.rstrip() for line in lines]
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return "\n".join(trimmed)


def order_test_cases(test_cases: Iterable[TestCase]) -> list[TestCase]:
    """Samples first, then by explicit order, then by id for determinism."""
    return sorted(
        test_cases,
        key=lambda tc: (not tc.is_sample, tc.order_index, tc.id or 0),
    )


def judge_submission(
    *,
    source_code: str,
    language: str,
    test_cases: Sequence[TestCase],
    time_limit_ms: int | None = None,
    memory_limit_mb: int | None = None,
) -> JudgeReport:
    """Evaluate ``source_code`` against ``test_cases`` and produce a verdict."""

    backend = get_backend()
    time_limit_ms = time_limit_ms or settings.EXECUTION_TIME_LIMIT_MS
    memory_limit_mb = memory_limit_mb or settings.EXECUTION_MEMORY_LIMIT_MB

    ordered = order_test_cases(test_cases)
    total = len(ordered)

    if total == 0:
        return JudgeReport(
            verdict=Verdict.INTERNAL_ERROR.value,
            score=0,
            passed_tests=0,
            total_tests=0,
            execution_time_ms=0.0,
            memory_kb=0,
            backend=backend.name,
            error_message="This problem has no test cases yet.",
        )

    reports: list[TestCaseReport] = []
    passed = 0
    peak_time_ms = 0.0
    peak_memory_kb = 0

    for index, test_case in enumerate(ordered, start=1):
        result = backend.run(
            ExecutionRequest(
                language=language,
                source_code=source_code,
                stdin=test_case.input_data,
                time_limit_ms=time_limit_ms,
                memory_limit_mb=memory_limit_mb,
                max_output_bytes=settings.EXECUTION_MAX_OUTPUT_BYTES,
            )
        )

        # Report the *worst* observed time/memory rather than a sum, which is
        # what a per-submission limit is actually measured against.
        peak_time_ms = max(peak_time_ms, result.duration_ms)
        peak_memory_kb = max(peak_memory_kb, result.memory_kb)

        if result.outcome is not Outcome.OK:
            verdict = _OUTCOME_TO_VERDICT.get(result.outcome, Verdict.RUNTIME_ERROR)
            reports.append(
                _build_report(index, test_case, False, verdict.value, result)
            )
            return JudgeReport(
                verdict=verdict.value,
                score=_score(passed, total),
                passed_tests=passed,
                total_tests=total,
                execution_time_ms=round(peak_time_ms, 2),
                memory_kb=peak_memory_kb,
                backend=result.backend,
                error_message=_error_message(result),
                failed_test_index=index,
                test_results=reports,
            )

        expected = normalise_output(test_case.expected_output)
        actual = normalise_output(result.stdout)

        if expected != actual:
            reports.append(
                _build_report(
                    index, test_case, False, Verdict.WRONG_ANSWER.value, result
                )
            )
            return JudgeReport(
                verdict=Verdict.WRONG_ANSWER.value,
                score=_score(passed, total),
                passed_tests=passed,
                total_tests=total,
                execution_time_ms=round(peak_time_ms, 2),
                memory_kb=peak_memory_kb,
                backend=result.backend,
                failed_test_index=index,
                test_results=reports,
            )

        passed += 1
        reports.append(
            _build_report(index, test_case, True, Verdict.ACCEPTED.value, result)
        )

    return JudgeReport(
        verdict=Verdict.ACCEPTED.value,
        score=100,
        passed_tests=passed,
        total_tests=total,
        execution_time_ms=round(peak_time_ms, 2),
        memory_kb=peak_memory_kb,
        backend=backend.name,
        test_results=reports,
    )


def run_once(
    *,
    source_code: str,
    language: str,
    stdin: str,
    time_limit_ms: int | None = None,
    memory_limit_mb: int | None = None,
) -> ExecutionResult:
    """Single run against custom input - powers the "Run" (vs "Submit") button."""
    backend = get_backend()
    return backend.run(
        ExecutionRequest(
            language=language,
            source_code=source_code,
            stdin=stdin,
            time_limit_ms=time_limit_ms or settings.EXECUTION_TIME_LIMIT_MS,
            memory_limit_mb=memory_limit_mb or settings.EXECUTION_MEMORY_LIMIT_MB,
            max_output_bytes=settings.EXECUTION_MAX_OUTPUT_BYTES,
        )
    )


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _score(passed: int, total: int) -> int:
    return int(round(passed * 100 / total)) if total else 0


def _build_report(
    index: int,
    test_case: TestCase,
    passed: bool,
    verdict: str,
    result: ExecutionResult,
) -> TestCaseReport:
    report = TestCaseReport(
        index=index,
        is_sample=bool(test_case.is_sample),
        passed=passed,
        verdict=verdict,
        execution_time_ms=result.duration_ms,
        memory_kb=result.memory_kb,
    )

    # Only sample data is safe to echo back; hidden cases stay opaque.
    if test_case.is_sample:
        report.input_data = test_case.input_data
        report.expected_output = normalise_output(test_case.expected_output)
        report.actual_output = normalise_output(result.stdout)
        report.stderr = result.stderr or None

    return report


def _error_message(result: ExecutionResult) -> str | None:
    if result.outcome is Outcome.COMPILE_ERROR:
        text = result.compile_output or "Compilation failed"
    elif result.outcome is Outcome.INTERNAL_ERROR:
        text = result.detail or "The judge could not execute this submission"
    elif result.outcome is Outcome.RUNTIME_ERROR:
        text = result.stderr or f"Process exited with code {result.exit_code}"
    elif result.outcome is Outcome.OUTPUT_EXCEEDED:
        text = "Program produced more output than the judge accepts"
    else:
        return None

    return text.strip()[:MAX_ERROR_CHARS] or None
