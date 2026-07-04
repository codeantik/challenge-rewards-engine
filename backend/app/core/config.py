from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. See .env.example for the full list."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/challenge_rewards"

    # Single fixed timezone driving streak-day bucketing and the Monday weekly
    # reset (invariant #6 in CLAUDE.md) — never per-user.
    forum_timezone: str = "UTC"

    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
