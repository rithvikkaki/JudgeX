"""JWT issue/verify helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_TYPE = "access"


def create_access_token(
    subject: str, *, extra_claims: dict | None = None, expires_minutes: int | None = None
) -> tuple[str, int]:
    """Return ``(token, lifetime_seconds)`` for ``subject``.

    ``subject`` is the user id as a string: unlike an email it never changes,
    so a token stays valid if the user updates their address.
    """
    lifetime_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=lifetime_minutes)

    claims = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": TOKEN_TYPE,
    }
    if extra_claims:
        claims.update(extra_claims)

    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, lifetime_minutes * 60


def decode_access_token(token: str) -> dict | None:
    """Return the claims, or ``None`` if the token is invalid or expired."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            # Passing the algorithm explicitly is what prevents an attacker
            # from presenting an `alg: none` or HMAC-vs-RSA confusion token.
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as exc:
        logger.debug("Rejected token: %s", exc)
        return None

    if payload.get("type") != TOKEN_TYPE:
        return None

    return payload
