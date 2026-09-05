from __future__ import annotations

from pydantic import BaseModel, Field


class LeaderboardProblemCell(BaseModel):
    """One participant's standing on one contest problem."""

    problem_id: int
    label: str | None = None
    solved: bool
    attempts: int
    points: int
    #: Minutes from contest start to the accepted submission.
    solved_at_minutes: int | None = None


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    solved: int = Field(description="Distinct contest problems accepted")
    score: int = Field(description="Sum of points for accepted problems")
    penalty: int = Field(
        description="ICPC-style penalty: minutes to each solve, plus a fixed "
        "penalty per rejected attempt on problems eventually solved"
    )
    problems: list[LeaderboardProblemCell] = []


class LeaderboardResponse(BaseModel):
    contest_id: int
    contest_title: str
    state: str
    total_participants: int
    entries: list[LeaderboardEntry]
