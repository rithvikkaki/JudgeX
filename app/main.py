"""FastAPI application factory and wiring."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine
from app.limiter import limiter
from app.models import Base  # noqa: F401 - registers every table on the metadata
from app.routes import api_router

logging.basicConfig(
    level=logging.INFO if not settings.is_production else logging.WARNING,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("judge")

API_PREFIX = "/api/v1"

DESCRIPTION = """
A competitive-programming judge backend.

**Authentication** - `POST /api/v1/auth/register` or `/auth/login` returns a
bearer token. Click **Authorize** and paste it (Swagger's form posts your email
in the `username` field).

**Roles** - reading is public; creating or editing problems, test cases and
contests requires an administrator account. Add your email to `ADMIN_EMAILS`
before registering to become one.

**Execution** - submitted code runs in a sandbox with the network disabled and
hard memory, CPU and wall-clock ceilings. `GET /api/v1/health` reports which
backend is active.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s (%s) against %s",
        settings.PROJECT_NAME,
        settings.ENVIRONMENT,
        "sqlite" if settings.is_sqlite else "postgresql",
    )

    # Idempotent: creates only what is missing. Safe to run on every boot,
    # which is what makes a fresh Render/Neon deployment work with no manual
    # migration step.
    Base.metadata.create_all(bind=engine)

    from app.execution.engine import get_backend

    backend = get_backend()
    logger.info("Execution backend: %s", backend.name)

    yield

    logger.info("Shutting down")
    engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Flatten Pydantic errors into a shape a client can render directly."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation failed",
            "errors": [
                {
                    "field": ".".join(str(part) for part in error["loc"][1:]) or "body",
                    "message": error["msg"],
                }
                for error in exc.errors()
            ],
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Log the driver message, return a generic one: database errors routinely
    # echo table and column names back to the caller.
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "A database error occurred. Please retry shortly."},
    )


app.include_router(api_router, prefix=API_PREFIX)


@app.get("/", tags=["System"], summary="Service banner")
def root() -> dict:
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": f"{API_PREFIX}/health",
        "api_prefix": API_PREFIX,
    }
