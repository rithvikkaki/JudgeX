from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMModel


class ContestRegistrationResponse(ORMModel):
    id: int
    contest_id: int
    user_id: int
    registered_at: datetime


class ParticipantResponse(ORMModel):
    id: int
    username: str
    registered_at: datetime
