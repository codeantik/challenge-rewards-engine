"""The strategy registry — the *only* place `challenge.type` is switched on
(CLAUDE.md invariant #3). `app/services/evaluator.py` never branches on
`type` itself; it looks the strategy up in `STRATEGIES` and calls the same
two methods on whichever one it gets back. Adding a challenge type means
adding one `ChallengeStrategy` implementation and one registry entry —
nothing else in `evaluator.py`, the admin schema, or the worker changes.

Both existing strategies recompute their result from the raw `events` table
on every call rather than incrementing a stored counter. That's what makes
progress-writing idempotent under CLAUDE.md invariant #5 ("the worker can
run a job twice safely"): recomputing "count of matching events in the
window" or "the day-streak ending today" from source data yields the same
answer no matter how many times you ask it, so there's no double-counting
step to guard against in the first place.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.challenge import Challenge
from app.models.event import Event


@dataclass(frozen=True)
class StrategyResult:
    current_value: int
    target_value: int
    is_complete: bool


class ChallengeStrategy(Protocol):
    def validate_config(self, rule_config: dict[str, Any]) -> None:
        """Raise `ValueError` if `rule_config` is missing/malformed for this
        type. Called from the admin schema layer so bad configs are
        rejected at write time, not discovered by a confused worker later.
        """
        ...

    async def evaluate(
        self, db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge
    ) -> StrategyResult:
        """Compute this user's current progress on `challenge` from scratch."""
        ...


def _require_positive_int(rule_config: dict[str, Any], key: str) -> int:
    value = rule_config.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"rule_config.{key} must be a positive integer")
    return value


class CountStrategy:
    """`{"target": N}` — complete once `event_type` has fired N times for
    this user inside the challenge's `[start_at, end_at]` window (either
    bound may be open).
    """

    def validate_config(self, rule_config: dict[str, Any]) -> None:
        _require_positive_int(rule_config, "target")

    async def evaluate(
        self, db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge
    ) -> StrategyResult:
        target = _require_positive_int(challenge.rule_config, "target")

        stmt = select(func.count()).select_from(Event).where(
            Event.user_id == user_id, Event.event_type == challenge.event_type
        )
        if challenge.start_at is not None:
            stmt = stmt.where(Event.created_at >= challenge.start_at)
        if challenge.end_at is not None:
            stmt = stmt.where(Event.created_at <= challenge.end_at)

        current = await db.scalar(stmt) or 0
        return StrategyResult(
            current_value=min(current, target), target_value=target, is_complete=current >= target
        )


def compute_streak(days: set[date], today: date) -> tuple[int, int]:
    """Given the distinct set of days (already bucketed into the forum
    timezone) a qualifying event happened on, return `(current_streak,
    best_streak)`.

    **Grace rule (documented per explain.md's ask):** the current streak is
    the consecutive run ending on the most recent active day, *as long as*
    that day is today or yesterday. A day with no activity *yet* (today,
    still in progress) doesn't break the streak; a full day skipped
    (nothing yesterday either) does. Best streak is just the longest
    consecutive run ever, independent of "today".
    """
    if not days:
        return 0, 0

    sorted_days = sorted(days)

    best = run = 1
    for prev, cur in zip(sorted_days, sorted_days[1:], strict=False):
        run = run + 1 if (cur - prev).days == 1 else 1
        best = max(best, run)

    last_active = sorted_days[-1]
    if (today - last_active).days > 1:
        return 0, best

    current = 1
    cursor = last_active
    day_set = days
    while (cursor - timedelta(days=1)) in day_set:
        cursor -= timedelta(days=1)
        current += 1
    return current, best


class StreakStrategy:
    """`{"length": N}` — complete once the user has a run of N consecutive
    forum-TZ days with at least one qualifying event.
    """

    def validate_config(self, rule_config: dict[str, Any]) -> None:
        _require_positive_int(rule_config, "length")

    async def evaluate(
        self, db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge
    ) -> StrategyResult:
        length = _require_positive_int(challenge.rule_config, "length")
        tz = ZoneInfo(get_settings().forum_timezone)

        stmt = select(Event.created_at).where(
            Event.user_id == user_id, Event.event_type == challenge.event_type
        )
        if challenge.start_at is not None:
            stmt = stmt.where(Event.created_at >= challenge.start_at)
        if challenge.end_at is not None:
            stmt = stmt.where(Event.created_at <= challenge.end_at)

        timestamps = (await db.scalars(stmt)).all()
        days = {ts.astimezone(tz).date() for ts in timestamps}
        today = datetime.now(tz).date()

        current, _best = compute_streak(days, today)
        return StrategyResult(
            current_value=min(current, length), target_value=length, is_complete=current >= length
        )


STRATEGIES: dict[str, ChallengeStrategy] = {
    "count": CountStrategy(),
    "streak": StreakStrategy(),
}
