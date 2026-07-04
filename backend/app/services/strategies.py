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
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.challenge import Challenge, ChallengePeriod
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


def week_start(now: datetime, tz: ZoneInfo) -> datetime:
    """Monday 00:00 in the forum timezone containing `now` — the lower
    bound of "this week" (CLAUDE.md invariant #6). Returned tz-aware in UTC
    so it compares directly against `Event.created_at`.
    """
    local_now = now.astimezone(tz)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    local_midnight = datetime.combine(monday, time.min, tzinfo=tz)
    return local_midnight.astimezone(UTC)


def effective_window(
    challenge: Challenge, *, now: datetime, tz: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """The event window a strategy counts within: the challenge's own
    `[start_at, end_at]`, clipped to "this week" when `period == weekly` so
    progress — and therefore the reward, via `completion_key` — resets every
    Monday. `period` is orthogonal to `type` (CLAUDE.md invariant #3 only
    restricts branching on `type`), so both strategies apply this the same
    way rather than the evaluator special-casing one of them.
    """
    start_at = challenge.start_at
    if challenge.period == ChallengePeriod.weekly.value:
        ws = week_start(now, tz)
        start_at = max(start_at, ws) if start_at is not None else ws
    return start_at, challenge.end_at


class CountStrategy:
    """`{"target": N}` — complete once `event_type` has fired N times for
    this user inside the challenge's effective window (`[start_at, end_at]`,
    further clipped to the current week for `period=weekly` challenges).
    """

    def validate_config(self, rule_config: dict[str, Any]) -> None:
        _require_positive_int(rule_config, "target")

    async def evaluate(
        self, db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge
    ) -> StrategyResult:
        target = _require_positive_int(challenge.rule_config, "target")
        tz = ZoneInfo(get_settings().forum_timezone)
        start_at, end_at = effective_window(challenge, now=datetime.now(UTC), tz=tz)

        stmt = select(func.count()).select_from(Event).where(
            Event.user_id == user_id, Event.event_type == challenge.event_type
        )
        if start_at is not None:
            stmt = stmt.where(Event.created_at >= start_at)
        if end_at is not None:
            stmt = stmt.where(Event.created_at <= end_at)

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


async def _fetch_qualifying_days(
    db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge, tz: ZoneInfo, now: datetime
) -> set[date]:
    start_at, end_at = effective_window(challenge, now=now, tz=tz)

    stmt = select(Event.created_at).where(
        Event.user_id == user_id, Event.event_type == challenge.event_type
    )
    if start_at is not None:
        stmt = stmt.where(Event.created_at >= start_at)
    if end_at is not None:
        stmt = stmt.where(Event.created_at <= end_at)

    timestamps = (await db.scalars(stmt)).all()
    return {ts.astimezone(tz).date() for ts in timestamps}


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
        now = datetime.now(UTC)

        days = await _fetch_qualifying_days(
            db, user_id=user_id, challenge=challenge, tz=tz, now=now
        )
        today = now.astimezone(tz).date()

        current, _best = compute_streak(days, today)
        return StrategyResult(
            current_value=min(current, length), target_value=length, is_complete=current >= length
        )


STRATEGIES: dict[str, ChallengeStrategy] = {
    "count": CountStrategy(),
    "streak": StreakStrategy(),
}

# Challenge types that are "streak-shaped", derived from the registry rather
# than hardcoded — used by the `/users/me/streaks` read endpoint to pick
# which active challenges to report on without a second `type == "streak"`
# literal anywhere in the codebase.
STREAK_CHALLENGE_TYPES: frozenset[str] = frozenset(
    name for name, strategy in STRATEGIES.items() if isinstance(strategy, StreakStrategy)
)


async def compute_user_streak(
    db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge
) -> tuple[int, int]:
    """`(current_streak, best_streak)`, recomputed directly from source
    events for the `/users/me/streaks` read endpoint. Not read from the
    `progress` cache: that table only stores the length-capped
    `current_value` needed to decide completion, not `best`.
    """
    tz = ZoneInfo(get_settings().forum_timezone)
    now = datetime.now(UTC)
    days = await _fetch_qualifying_days(db, user_id=user_id, challenge=challenge, tz=tz, now=now)
    return compute_streak(days, now.astimezone(tz).date())
