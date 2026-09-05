from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.submission import SubmissionSummary


class VerdictCount(BaseModel):
    verdict: str
    count: int


class DifficultyProgress(BaseModel):
    difficulty: str
    solved: int
    total_available: int


class LanguageUsage(BaseModel):
    language: str
    submissions: int
    accepted: int


class DashboardResponse(BaseModel):
    username: str
    email: str

    total_submissions: int
    accepted_submissions: int
    acceptance_rate: float = Field(description="Accepted / total, as a percentage")
    problems_solved: int
    problems_attempted: int

    contests_participated: int
    best_contest_rank: int | None = None

    verdict_breakdown: list[VerdictCount] = []
    difficulty_progress: list[DifficultyProgress] = []
    language_usage: list[LanguageUsage] = []
    recent_submissions: list[SubmissionSummary] = []
