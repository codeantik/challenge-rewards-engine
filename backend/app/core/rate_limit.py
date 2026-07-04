"""In-memory token-bucket rate limiting for `POST /api/events` (bonus, per
CLAUDE.md's phase map: "rate limiting on /api/events" is the highest-priority
bonus item after unit tests).

Why in-memory and not Redis: this repo already made this exact trade-off
once for the job queue (Postgres outbox over Celery+Redis — see explain.md
§3) on the grounds that the most *explainable* infra that satisfies the
requirement beats the more "correct" one for a 5-day, single-reviewer
submission. The same reasoning applies here — a dict keyed by user id needs
no new infrastructure and is trivial to reason about and test. The trade-off,
spelled out rather than hidden: state is per-process, so the ceiling is per
uvicorn worker, not global across replicas. Swapping in Redis (`INCR` + TTL,
or a Lua-scripted token bucket) later is a localized change to this one
module.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from app.core.errors import AppError


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


@dataclass
class TokenBucketRateLimiter:
    """Classic token bucket: `capacity` tokens, refilling continuously at
    `capacity / refill_seconds` tokens/sec. One `check()` call spends one
    token; raises `AppError("RATE_LIMITED", ..., 429)` when the bucket is
    empty. Refill is computed from elapsed wall-clock time on each call
    rather than a background timer, so an idle bucket costs nothing.
    """

    capacity: int
    refill_seconds: float
    _buckets: dict[uuid.UUID, _Bucket] = field(default_factory=dict)

    def check(self, key: uuid.UUID, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(self.capacity), updated_at=now)
            self._buckets[key] = bucket

        refill_rate = self.capacity / self.refill_seconds
        elapsed = max(0.0, now - bucket.updated_at)
        bucket.tokens = min(self.capacity, bucket.tokens + elapsed * refill_rate)
        bucket.updated_at = now

        if bucket.tokens < 1:
            retry_after = (1 - bucket.tokens) / refill_rate
            raise AppError(
                "RATE_LIMITED",
                "too many events submitted; slow down and retry shortly",
                status_code=429,
                details={"retry_after_seconds": round(retry_after, 1)},
            )

        bucket.tokens -= 1
