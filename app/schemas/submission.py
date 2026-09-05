from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.enums import Language
from app.schemas.common import ORMModel

MAX_SOURCE_BYTES = 100_000


class SubmissionCreate(BaseModel):
    problem_id: int
    language: Language
    source_code: str = Field(min_length=1, max_length=MAX_SOURCE_BYTES)
    contest_id: int | None = Field(
        default=None,
        description="Scope this submission to a contest. Requires an active "
        "registration and a running contest window.",
    )


class RunRequest(BaseModel):
    """Ad-hoc execution against custom input; nothing is persisted."""

    language: Language
    source_code: str = Field(min_length=1, max_length=MAX_SOURCE_BYTES)
    stdin: str = ""
    problem_id: int | None = Field(
        default=None, description="Inherit this problem's time/memory limits"
    )


class RunResponse(BaseModel):
    outcome: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    memory_kb: int
    compile_output: str | None = None
    backend: str


class TestCaseResult(BaseModel):
    index: int
    is_sample: bool
    passed: bool
    verdict: str
    execution_time_ms: float
    memory_kb: int
    # Present for sample cases only - hidden cases never expose their data.
    input_data: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None
    stderr: str | None = None


class SubmissionSummary(ORMModel):
    id: int
    user_id: int
    problem_id: int
    contest_id: int | None
    language: str
    status: str
    verdict: str
    score: int
    passed_tests: int
    total_tests: int
    execution_time_ms: float
    memory_kb: int
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def execution_time_display(self) -> str:
        return f"{self.execution_time_ms:.2f} ms"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def memory_display(self) -> str:
        if self.memory_kb >= 1024:
            return f"{self.memory_kb / 1024:.2f} MB"
        return f"{self.memory_kb} KB"


class SubmissionResponse(SubmissionSummary):
    source_code: str
    error_message: str | None = None
    failed_test_index: int | None = None


class SubmissionDetail(SubmissionResponse):
    """Returned straight after judging, with the per-test breakdown."""

    problem_title: str | None = None
    backend: str | None = None
    test_results: list[TestCaseResult] = []
