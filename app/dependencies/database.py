from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from app.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Request-scoped session.

    Rolls back on an unhandled exception so a failed request can never leave a
    half-applied transaction behind for the next borrower of this connection.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
