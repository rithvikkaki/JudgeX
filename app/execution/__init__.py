"""Sandboxed code execution and verdict generation."""

from app.execution.base import ExecutionRequest, ExecutionResult, Outcome
from app.execution.engine import backend_status, get_backend
from app.execution.judge import JudgeReport, TestCaseReport, judge_submission, run_once
from app.execution.languages import LANGUAGES, get_language, supported_languages

__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "Outcome",
    "JudgeReport",
    "TestCaseReport",
    "LANGUAGES",
    "backend_status",
    "get_backend",
    "get_language",
    "judge_submission",
    "run_once",
    "supported_languages",
]
