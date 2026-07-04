"""Reward disbursal — CLAUDE.md invariant #4, idempotency place #2.

Called by the evaluator, in the same transaction as the progress upsert,
whenever a strategy reports `is_complete`. Disbursal is a plain
insert-or-ignore against the `rewards` table's own unique constraint — not
an application-level "check if it exists, then insert" — so it's safe to
call on every evaluation that finds a challenge complete, including repeat
evaluations of an already-completed one (invariant #5: the worker can run a
job twice).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.challenge import Challenge, ChallengePeriod
from app.models.reward import Reward


def completion_key(challenge: Challenge, *, now: datetime, tz: ZoneInfo) -> str:
    """`"once"` for a one-shot challenge — any later completion is the same
    key, so the unique constraint blocks a second payout forever. The ISO
    week (e.g. `"2026-W27"`) for a weekly challenge — a new week is a new
    key, so it's a fresh completion each Monday (CLAUDE.md invariant #6).
    A pure function of `(challenge, now, tz)` so the rollover behavior is
    unit-testable without freezing the wall clock.
    """
    if challenge.period == ChallengePeriod.weekly.value:
        iso_year, iso_week, _ = now.astimezone(tz).date().isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return "once"


async def disburse_reward(db: AsyncSession, *, user_id: uuid.UUID, challenge: Challenge) -> None:
    tz = ZoneInfo(get_settings().forum_timezone)
    key = completion_key(challenge, now=datetime.now(UTC), tz=tz)

    stmt = (
        pg_insert(Reward)
        .values(
            user_id=user_id,
            reward_type=challenge.reward.get("type", "points"),
            amount=challenge.reward.get("amount", 0),
            source_challenge_id=challenge.id,
            completion_key=key,
        )
        .on_conflict_do_nothing(
            index_elements=[Reward.user_id, Reward.source_challenge_id, Reward.completion_key]
        )
    )
    await db.execute(stmt)
