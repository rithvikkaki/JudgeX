"""SQLAlchemy engine and session factory.

Supports Postgres (local Docker or a hosted provider such as Neon) and SQLite
for zero-setup local development.  Connection arguments differ per dialect, so
they are assembled here rather than sprinkled through the app.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _build_engine() -> Engine:
    kwargs: dict = {
        "echo": settings.DB_ECHO,
        "future": True,
        # Hosted Postgres (Neon in particular) closes idle connections
        # aggressively.  Verify a connection before handing it out, and recycle
        # well inside the provider's idle timeout.
        "pool_pre_ping": True,
    }

    if settings.is_sqlite:
        # SQLite needs this to be usable from FastAPI's threadpool.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        kwargs["pool_recycle"] = 280
        kwargs["connect_args"] = {
            # Fail fast instead of hanging when the database is unreachable.
            "connect_timeout": 10,
            "application_name": "online-coding-judge",
        }

    return create_engine(settings.DATABASE_URL, **kwargs)


engine: Engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)
