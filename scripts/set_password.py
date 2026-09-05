"""Change an existing account's password without touching any other data.

Use this instead of re-seeding, which would drop every table.

    python scripts/set_password.py you@example.com

The password is read from a hidden prompt, so it never appears in your shell
history or terminal scrollback. Pass ``--from-env`` to read it from
``NEW_PASSWORD`` instead, for non-interactive use.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.utils.security import MAX_PASSWORD_BYTES, hash_password  # noqa: E402

MIN_LENGTH = 8


def main() -> int:
    parser = argparse.ArgumentParser(description="Set a user's password")
    parser.add_argument("email", help="email address of the account to update")
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="read the new password from the NEW_PASSWORD variable",
    )
    parser.add_argument(
        "--make-admin",
        action="store_true",
        help="also grant administrator rights to this account",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(func.lower(User.email) == args.email.strip().lower())
        )
        if user is None:
            print(f"No account found for {args.email!r}.")
            return 1

        print(f"Account: {user.username} <{user.email}>  admin={user.is_admin}")

        if args.from_env:
            password = os.environ.get("NEW_PASSWORD", "")
            if not password:
                print("NEW_PASSWORD is not set.")
                return 1
        else:
            password = getpass.getpass("New password: ")
            if password != getpass.getpass("Confirm password: "):
                print("Passwords did not match.")
                return 1

        problem = _validate(password)
        if problem:
            print(problem)
            return 1

        user.hashed_password = hash_password(password)
        if args.make_admin:
            user.is_admin = True

        db.commit()

    print("Password updated. Existing tokens stay valid until they expire.")
    return 0


def _validate(password: str) -> str | None:
    """Mirror the rules enforced by the registration schema."""
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters."
    if password.isdigit() or password.isalpha():
        return "Password must mix letters with digits or symbols."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
    return None


if __name__ == "__main__":
    raise SystemExit(main())
