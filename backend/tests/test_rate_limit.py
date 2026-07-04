from __future__ import annotations

import uuid

import pytest

from app.core.errors import AppError
from app.core.rate_limit import TokenBucketRateLimiter


def test_allows_up_to_capacity_then_blocks() -> None:
    limiter = TokenBucketRateLimiter(capacity=3, refill_seconds=60)
    key = uuid.uuid4()

    for _ in range(3):
        limiter.check(key, now=0.0)

    with pytest.raises(AppError) as exc_info:
        limiter.check(key, now=0.0)
    assert exc_info.value.code == "RATE_LIMITED"
    assert exc_info.value.status_code == 429


def test_refills_continuously_over_time() -> None:
    limiter = TokenBucketRateLimiter(capacity=2, refill_seconds=60)
    key = uuid.uuid4()

    limiter.check(key, now=0.0)
    limiter.check(key, now=0.0)
    with pytest.raises(AppError):
        limiter.check(key, now=0.0)

    # Half the window has elapsed -> one token back.
    limiter.check(key, now=30.0)
    with pytest.raises(AppError):
        limiter.check(key, now=30.0)


def test_buckets_are_independent_per_key() -> None:
    limiter = TokenBucketRateLimiter(capacity=1, refill_seconds=60)
    a, b = uuid.uuid4(), uuid.uuid4()

    limiter.check(a, now=0.0)
    with pytest.raises(AppError):
        limiter.check(a, now=0.0)

    # A different key's bucket is untouched by A's exhaustion.
    limiter.check(b, now=0.0)


def test_never_exceeds_capacity_after_a_long_idle_period() -> None:
    limiter = TokenBucketRateLimiter(capacity=2, refill_seconds=60)
    key = uuid.uuid4()

    limiter.check(key, now=0.0)
    # A huge idle gap refills the bucket back to capacity, not beyond it —
    # so exactly `capacity` checks succeed afterward, no more.
    limiter.check(key, now=10_000.0)
    limiter.check(key, now=10_000.0)
    with pytest.raises(AppError):
        limiter.check(key, now=10_000.0)
