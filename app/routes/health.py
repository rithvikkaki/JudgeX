"""Liveness and readiness endpoints.

Platforms such as Render poll ``/api/v1/health`` to decide whether an instance
is healthy; it must stay cheap and must not require authentication.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies.database import get_db
from app.execution.engine import backend_status
from app.execution.languages import supported_languages

router = APIRouter(tags=["System"])


@router.get("/health", summary="Service health")
def health(response: Response, db: Session = Depends(get_db)) -> dict:
    started = time.perf_counter()

    try:
        db.execute(text("SELECT 1"))
        database = {
            "connected": True,
            "dialect": db.bind.dialect.name if db.bind else "unknown",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 - the payload reports the failure
        database = {"connected": False, "error": f"{type(exc).__name__}: {exc}"}
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if database["connected"] else "degraded",
        "version": settings.API_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": database,
        "execution": backend_status(),
        "languages": [lang["id"] for lang in supported_languages()],
    }


@router.get("/ping", summary="Cheap liveness probe")
def ping() -> dict:
    return {"status": "ok"}
