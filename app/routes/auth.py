from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and receive a token",
)
@limiter.limit(lambda: settings.RATE_LIMIT_AUTH)
def register(
    request: Request, payload: UserCreate, db: Session = Depends(get_db)
) -> Token:
    email = payload.email.lower()

    clash = db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == email,
                func.lower(User.username) == payload.username.lower(),
            )
        )
    )
    if clash is not None:
        field = "Email" if clash.email.lower() == email else "Username"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{field} is already registered",
        )

    user = User(
        username=payload.username,
        email=email,
        hashed_password=hash_password(payload.password),
        # Bootstrapping: emails listed in ADMIN_EMAILS become admins on signup,
        # so a fresh deployment has someone who can author problems.
        is_admin=email in settings.admin_email_set,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique index is the real arbiter; the check above is only a
        # friendlier fast path and two concurrent signups can both pass it.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email is already registered",
        ) from None

    db.refresh(user)
    return _issue_token(user)


@router.post("/login", response_model=Token, summary="Exchange credentials for a token")
@limiter.limit(lambda: settings.RATE_LIMIT_AUTH)
def login(
    request: Request, payload: UserLogin, db: Session = Depends(get_db)
) -> Token:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))

    # Verify against a dummy hash when the user is missing so that a wrong
    # email and a wrong password take the same time and leak nothing.
    if user is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise _invalid_credentials()

    if not verify_password(payload.password, user.hashed_password):
        raise _invalid_credentials()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
        )

    return _issue_token(user)


@router.post(
    "/token",
    response_model=Token,
    include_in_schema=False,
    summary="OAuth2 password flow (used by the Swagger Authorize button)",
)
def login_form(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    # Swagger's Authorize dialog posts `username`; users type their email there.
    return login(request, UserLogin(email=form.username, password=form.password), db)


@router.get("/me", response_model=UserResponse, summary="Current account")
def me(user: User = Depends(get_current_user)) -> User:
    return user


# ---------------------------------------------------------------------- #
def _issue_token(user: User) -> Token:
    token, expires_in = create_access_token(
        user.id, extra_claims={"username": user.username, "admin": user.is_admin}
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


#: A real bcrypt hash of a random string, used purely to equalise timing.
_DUMMY_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.6Nn7DXxKZKQXQ3qHxJZ5m5Q0YKQ8vXu"
