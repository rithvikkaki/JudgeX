from __future__ import annotations

from app.config import settings

try:
    from celery import Celery
except ImportError:  # pragma: no cover - exercised only without dependencies
    Celery = None  # type: ignore[assignment]


if Celery is not None:
    celery_app = Celery(
        "judgex",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=["app.tasks.submissions"],
    )
    celery_app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
    )
else:
    celery_app = None
