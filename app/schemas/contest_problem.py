from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.problem import ProblemSummary


class ContestProblemCreate(BaseModel):
    problem_id: int
    label: str | None = Field(
        default=None,
        max_length=8,
        description="Display label such as 'A'. Auto-assigned when omitted.",
    )
    points: int = Field(default=100, ge=1, le=10_000)
    order_index: int = Field(default=0, ge=0)


class ContestProblemUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=8)
    points: int | None = Field(default=None, ge=1, le=10_000)
    order_index: int | None = Field(default=None, ge=0)


class ContestProblemResponse(ORMModel):
    id: int
    contest_id: int
    problem_id: int
    label: str | None
    points: int
    order_index: int


class ContestProblemDetail(ContestProblemResponse):
    """A contest slot joined with the problem it points at."""

    problem: ProblemSummary
