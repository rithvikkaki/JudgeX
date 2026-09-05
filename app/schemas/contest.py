from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel


class ContestBase(BaseModel):
    title: str = Field(min_length=3, max_length=255, examples=["Weekly Round #1"])
    description: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    penalty_minutes_per_wrong: int = Field(default=20, ge=0, le=120)

    @field_validator("start_time", "end_time")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        # A naive timestamp is ambiguous across deployments; assume UTC and say so
        # in the docs rather than silently using the server's local zone.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @model_validator(mode="after")
    def _check_window(self) -> "ContestBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class ContestCreate(ContestBase):
    pass


class ContestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    penalty_minutes_per_wrong: int | None = Field(default=None, ge=0, le=120)


class ContestResponse(ORMModel):
    id: int
    slug: str
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    penalty_minutes_per_wrong: int
    state: str
    created_at: datetime

    problem_count: int = 0
    participant_count: int = 0
    is_registered: bool | None = None
