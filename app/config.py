"""Application settings.

Everything the app needs to run is declared here once, validated at import
time, and injected everywhere else via ``settings``.  A missing or malformed
value fails loudly at startup instead of producing a confusing error deep
inside a request handler.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application -----------------------------------------------------
    PROJECT_NAME: str = "JudgeX"
    API_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ---- Database --------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./online_judge.db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ---- Background jobs -------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # ---- Security --------------------------------------------------------
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ADMIN_EMAILS: str = ""

    # ---- Execution engine ------------------------------------------------
    EXECUTION_BACKEND: Literal["auto", "docker", "local"] = "auto"
    EXECUTION_TIME_LIMIT_MS: int = Field(default=2000, ge=100, le=30_000)
    EXECUTION_MEMORY_LIMIT_MB: int = Field(default=128, ge=16, le=2048)
    EXECUTION_CPU_QUOTA_PERCENT: int = Field(default=50, ge=5, le=100)
    EXECUTION_MAX_OUTPUT_BYTES: int = Field(default=64 * 1024, ge=1024)
    EXECUTION_PIDS_LIMIT: int = Field(default=64, ge=1)
    EXECUTION_COMPILE_TIMEOUT_S: int = Field(default=15, ge=1, le=120)
    ALLOW_UNSAFE_LOCAL_EXECUTION: bool = False

    # ---- Rate limiting ---------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_SUBMIT: str = "5/minute"
    RATE_LIMIT_RUN: str = "10/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    #: Directory used to stage sandbox scratch dirs.
    #:
    #: This matters when the API itself runs in a container and talks to the
    #: host's Docker socket. Bind-mount paths are resolved by the *daemon* on
    #: the *host*, so a path that exists only inside the API container silently
    #: mounts as empty. Pointing this at a directory bind-mounted to the same
    #: absolute path on both sides makes the path valid for both.
    EXECUTION_WORKDIR: str = ""

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.CORS_ORIGINS.strip()
        if not raw or raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def cors_allow_credentials(self) -> bool:
        """Allow credentials only if explicit origins are configured (never with wildcard '*')."""
        return "*" not in self.cors_origin_list

    @property
    def admin_email_set(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.ADMIN_EMAILS.split(",")
            if email.strip()
        }

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def execution_workdir(self) -> str | None:
        """Staging directory for sandbox runs, or ``None`` for the system temp."""
        return self.EXECUTION_WORKDIR.strip() or None

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL must not be empty")

        # Neon, Railway and Heroku hand out `postgres://` / `postgresql://`
        # URLs.  SQLAlchemy 2.x wants an explicit driver, so pin psycopg2.
        if value.startswith("postgres://"):
            value = "postgresql+psycopg2://" + value[len("postgres://") :]
        elif value.startswith("postgresql://"):
            value = "postgresql+psycopg2://" + value[len("postgresql://") :]

        return value

    @model_validator(mode="after")
    def _check_secret_key(self) -> "Settings":
        if not self.SECRET_KEY:
            if self.is_production:
                raise ValueError(
                    "SECRET_KEY must be set in production. Generate one with: "
                    'python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            # Development convenience: a per-process ephemeral key.  Tokens do
            # not survive a restart, which is fine locally and safe by default.
            object.__setattr__(self, "SECRET_KEY", secrets.token_urlsafe(64))

        if self.is_production and self.SECRET_KEY.startswith("CHANGE_ME"):
            raise ValueError("SECRET_KEY still holds the placeholder value")

        if not self.CELERY_BROKER_URL:
            object.__setattr__(self, "CELERY_BROKER_URL", self.REDIS_URL)
        if not self.CELERY_RESULT_BACKEND:
            object.__setattr__(self, "CELERY_RESULT_BACKEND", self.REDIS_URL)

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
