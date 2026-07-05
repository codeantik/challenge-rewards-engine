from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. See .env.example for the full list."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/challenge_rewards"
    # Derived from a `?sslmode=...` query param on `database_url` (see
    # `_normalize_database_url` below) — not meant to be set directly, though
    # an explicit `DATABASE_SSL=true` env var still works if ever needed.
    database_ssl: bool = False

    # Single fixed timezone driving streak-day bucketing and the Monday weekly
    # reset (invariant #6 in CLAUDE.md) — never per-user.
    forum_timezone: str = "UTC"

    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = ["http://localhost:3000"]
    # Optional regex for origins that vary per-deploy (e.g. Vercel preview
    # URLs like `https://<project>-<hash>.vercel.app`), additive to
    # `cors_origins`. `None` disables it (CORSMiddleware default).
    cors_origin_regex: str | None = None

    # Token-bucket limits for `POST /api/events` (see app/core/rate_limit.py).
    event_rate_limit_capacity: int = 20
    event_rate_limit_window_seconds: float = 60.0

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        """Managed Postgres providers (Render, Neon, Supabase, Heroku-style)
        hand out `postgres://`/`postgresql://` connection strings for the
        sync `psycopg` driver, often with a libpq `?sslmode=require` query
        param. SQLAlchemy needs the `asyncpg` dialect explicit in the scheme,
        and asyncpg's `connect()` doesn't understand `sslmode` as a kwarg —
        so rewrite the scheme and move `sslmode` into `database_ssl`
        (consumed as an asyncpg `ssl=True` connect arg by `app/core/db.py`
        and `alembic/env.py`) instead of asking every deploy target to
        hand-craft a SQLAlchemy-flavored URL.
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]

        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        sslmode = query.pop("sslmode", None)
        if sslmode in ("require", "verify-ca", "verify-full"):
            self.database_ssl = True
        url = urlunsplit(parts._replace(query=urlencode(query)))

        self.database_url = url
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
