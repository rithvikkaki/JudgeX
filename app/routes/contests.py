from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_admin, get_current_user, get_optional_user
from app.dependencies.database import get_db
from app.models.contest import Contest
from app.models.contest_problem import ContestProblem
from app.models.contest_registration import ContestRegistration
from app.models.enums import ContestState
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.contest import ContestCreate, ContestResponse, ContestUpdate
from app.schemas.contest_registration import (
    ContestRegistrationResponse,
    ParticipantResponse,
)
from app.schemas.leaderboard import LeaderboardResponse
from app.services.leaderboard import build_leaderboard
from app.utils.slug import unique_slug

router = APIRouter(prefix="/contests", tags=["Contests"])


@router.get("", response_model=Page[ContestResponse], summary="List contests")
def list_contests(
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
    state: ContestState | None = Query(default=None, description="Filter by state"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[ContestResponse]:
    now = datetime.now(timezone.utc)

    conditions = []
    # State is derived from the window, so filter it in SQL rather than
    # fetching everything and filtering in Python.
    if state is ContestState.UPCOMING:
        conditions.append(Contest.start_time > now)
    elif state is ContestState.RUNNING:
        conditions.extend([Contest.start_time <= now, Contest.end_time >= now])
    elif state is ContestState.ENDED:
        conditions.append(Contest.end_time < now)

    total = db.scalar(select(func.count(Contest.id)).where(*conditions)) or 0

    rows = list(
        db.scalars(
            select(Contest)
            .where(*conditions)
            .order_by(Contest.start_time.desc())
            .limit(limit)
            .offset(offset)
        )
    )

    return Page[ContestResponse](
        items=[_to_response(db, contest, viewer) for contest in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{identifier}", response_model=ContestResponse, summary="One contest by id or slug"
)
def get_contest(
    identifier: str,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> ContestResponse:
    return _to_response(db, _resolve(db, identifier), viewer)


@router.post(
    "",
    response_model=ContestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a contest (admin only)",
)
def create_contest(
    payload: ContestCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ContestResponse:
    contest = Contest(
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        penalty_minutes_per_wrong=payload.penalty_minutes_per_wrong,
        slug=unique_slug(payload.title, lambda s: _slug_taken(db, s)),
        created_by=admin.id,
    )
    db.add(contest)
    db.commit()
    db.refresh(contest)
    return _to_response(db, contest, admin)


@router.patch(
    "/{contest_id}",
    response_model=ContestResponse,
    summary="Update a contest (admin only)",
)
def update_contest(
    contest_id: int,
    payload: ContestUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ContestResponse:
    contest = db.get(Contest, contest_id)
    if contest is None:
        raise _not_found()

    changes = payload.model_dump(exclude_unset=True)

    for field in ("start_time", "end_time"):
        if changes.get(field) is not None and changes[field].tzinfo is None:
            changes[field] = changes[field].replace(tzinfo=timezone.utc)

    start = changes.get("start_time") or _aware(contest.start_time)
    end = changes.get("end_time") or _aware(contest.end_time)
    if end <= start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )

    if changes.get("title") and changes["title"] != contest.title:
        contest.slug = unique_slug(
            changes["title"], lambda s: _slug_taken(db, s, exclude_id=contest.id)
        )

    for field, value in changes.items():
        if value is not None:
            setattr(contest, field, value)

    db.commit()
    db.refresh(contest)
    return _to_response(db, contest, admin)


@router.delete(
    "/{contest_id}", response_model=Message, summary="Delete a contest (admin only)"
)
def delete_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Message:
    contest = db.get(Contest, contest_id)
    if contest is None:
        raise _not_found()

    db.delete(contest)
    db.commit()
    return Message(message="Contest deleted successfully")


# ---------------------------------------------------------------------- #
# Registration
# ---------------------------------------------------------------------- #
@router.post(
    "/{contest_id}/join",
    response_model=ContestRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register for a contest",
)
def join_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContestRegistration:
    contest = db.get(Contest, contest_id)
    if contest is None:
        raise _not_found()

    if contest.state is ContestState.ENDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This contest has already ended",
        )

    registration = ContestRegistration(contest_id=contest_id, user_id=user.id)
    db.add(registration)

    try:
        db.commit()
    except IntegrityError:
        # The unique (contest_id, user_id) constraint is authoritative, so two
        # simultaneous joins cannot both create a row.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already joined this contest",
        ) from None

    db.refresh(registration)
    return registration


@router.delete(
    "/{contest_id}/join", response_model=Message, summary="Withdraw from a contest"
)
def leave_contest(
    contest_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    registration = db.scalar(
        select(ContestRegistration).where(
            ContestRegistration.contest_id == contest_id,
            ContestRegistration.user_id == user.id,
        )
    )
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not registered for this contest",
        )

    db.delete(registration)
    db.commit()
    return Message(message="Withdrawn from contest")


@router.get(
    "/{contest_id}/participants",
    response_model=list[ParticipantResponse],
    summary="Registered participants",
)
def contest_participants(
    contest_id: int, db: Session = Depends(get_db)
) -> list[ParticipantResponse]:
    _require_contest(db, contest_id)

    rows = db.execute(
        select(User.id, User.username, ContestRegistration.registered_at)
        .join(ContestRegistration, ContestRegistration.user_id == User.id)
        .where(ContestRegistration.contest_id == contest_id)
        .order_by(ContestRegistration.registered_at)
    ).all()

    return [
        ParticipantResponse(id=row.id, username=row.username, registered_at=row.registered_at)
        for row in rows
    ]


@router.get(
    "/{contest_id}/leaderboard",
    response_model=LeaderboardResponse,
    summary="Score-ranked standings",
)
def contest_leaderboard(
    contest_id: int, db: Session = Depends(get_db)
) -> LeaderboardResponse:
    return build_leaderboard(db, _require_contest(db, contest_id))


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #
def _to_response(
    db: Session, contest: Contest, viewer: User | None
) -> ContestResponse:
    response = ContestResponse(
        id=contest.id,
        slug=contest.slug,
        title=contest.title,
        description=contest.description,
        start_time=contest.start_time,
        end_time=contest.end_time,
        duration_minutes=contest.duration_minutes,
        penalty_minutes_per_wrong=contest.penalty_minutes_per_wrong,
        state=contest.state.value,
        created_at=contest.created_at,
    )

    response.problem_count = (
        db.scalar(
            select(func.count(ContestProblem.id)).where(
                ContestProblem.contest_id == contest.id
            )
        )
        or 0
    )
    response.participant_count = (
        db.scalar(
            select(func.count(ContestRegistration.id)).where(
                ContestRegistration.contest_id == contest.id
            )
        )
        or 0
    )

    if viewer is not None:
        response.is_registered = (
            db.scalar(
                select(ContestRegistration.id).where(
                    ContestRegistration.contest_id == contest.id,
                    ContestRegistration.user_id == viewer.id,
                )
            )
            is not None
        )

    return response


def _resolve(db: Session, identifier: str) -> Contest:
    contest = (
        db.get(Contest, int(identifier))
        if identifier.isdigit()
        else db.scalar(select(Contest).where(Contest.slug == identifier))
    )
    if contest is None:
        raise _not_found()
    return contest


def _require_contest(db: Session, contest_id: int) -> Contest:
    contest = db.get(Contest, contest_id)
    if contest is None:
        raise _not_found()
    return contest


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
    )


def _slug_taken(db: Session, slug: str, exclude_id: int | None = None) -> bool:
    query = select(Contest.id).where(Contest.slug == slug)
    if exclude_id is not None:
        query = query.where(Contest.id != exclude_id)
    return db.scalar(query) is not None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
