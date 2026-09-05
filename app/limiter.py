"""Rate limiting configuration using slowapi."""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def _get_client_ip(request: Request) -> str:
    """Safely extract client IP, respecting X-Forwarded-For if present behind proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
        if client_ip:
            return client_ip
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_client_ip,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[],
)
