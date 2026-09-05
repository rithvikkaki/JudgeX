"""Model package.

Importing this module registers every table on ``Base.metadata``, which is
what ``Base.metadata.create_all()`` and the test fixtures rely on.
"""

from app.models.base import Base, TimestampMixin, utcnow
from app.models.contest import Contest
from app.models.contest_problem import ContestProblem
from app.models.contest_registration import ContestRegistration
from app.models.enums import (
    ContestState,
    Difficulty,
    Language,
    SubmissionStatus,
    Verdict,
)
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.test_case import TestCase
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "utcnow",
    "Contest",
    "ContestProblem",
    "ContestRegistration",
    "ContestState",
    "Difficulty",
    "Language",
    "Problem",
    "Submission",
    "SubmissionStatus",
    "TestCase",
    "User",
    "Verdict",
]
