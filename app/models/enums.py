"""Domain vocabularies shared by models and schemas.

These are stored as plain strings in the database (rather than native Postgres
ENUM types) so that adding a verdict never requires a schema migration.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """A ``str`` subclass enum that serialises to its value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class Difficulty(StrEnum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class Language(StrEnum):
    PYTHON = "python"
    CPP = "cpp"
    JAVA = "java"


class SubmissionStatus(StrEnum):
    """Lifecycle of a submission row, independent of its verdict."""

    QUEUED = "Queued"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class Verdict(StrEnum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    WRONG_ANSWER = "Wrong Answer"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
    RUNTIME_ERROR = "Runtime Error"
    COMPILATION_ERROR = "Compilation Error"
    OUTPUT_LIMIT_EXCEEDED = "Output Limit Exceeded"
    INTERNAL_ERROR = "Internal Error"


class ContestState(StrEnum):
    UPCOMING = "Upcoming"
    RUNNING = "Running"
    ENDED = "Ended"
