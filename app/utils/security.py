"""Password hashing.

Uses the ``bcrypt`` library directly rather than through passlib: passlib 1.7.4
reads ``bcrypt.__about__.__version__``, which modern bcrypt releases removed,
producing a spurious warning today and a hard failure on bcrypt 5.  Calling
bcrypt straight through is both fewer moving parts and stable.
"""

from __future__ import annotations

import bcrypt

#: bcrypt hashes at most 72 bytes of input and silently ignores the rest, which
#: would make two different long passwords interchangeable. Registration rejects
#: anything longer, and this guard keeps that invariant if it is ever bypassed.
MAX_PASSWORD_BYTES = 72

#: Work factor. 12 is the common 2020s default: ~250ms per hash on modern
#: hardware, slow enough to matter to an attacker, fast enough for a login.
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    encoded = _encode(password)
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(encoded, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            _encode(password), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        # Malformed or legacy hash - treat as a failed login, never a 500.
        return False


def _encode(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded"
        )
    return encoded
