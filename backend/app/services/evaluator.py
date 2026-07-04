"""The generic, data-driven evaluator (CLAUDE.md invariant #3, #5).

Called by the worker with one `Event`; finds every currently-active
challenge listening for that `event_type`, asks the strategy registry to
compute the affected user's progress, and upserts the result. This module
never branches on `challenge.type` — that's `app/services/strategies.py`'s
job alone.

Doesn't commit — the caller (the worker, in the same transaction as the job
status update) owns that, same convention as `ingest_event`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge, ChallengeStatus
from app.models.event import Event
from app.models.progress import Progress
from app.services.rewards import disburse_reward
from app.services.strategies import STRATEGIES, StrategyResult


async def _upsert_progress(
    db: AsyncSession, *, user_id: uuid.UUID, challenge_id: uuid.UUID, result: StrategyResult
) -> None:
    stmt = pg_insert(Progress).values(
        user_id=user_id,
        challenge_id=challenge_id,
        current_value=result.current_value,
        target_value=result.target_value,
        is_complete=result.is_complete,
        completed_at=func.now() if result.is_complete else None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Progress.user_id, Progress.challenge_id],
        set_={
            "current_value": stmt.excluded.current_value,
            "target_value": stmt.excluded.target_value,
            "is_complete": stmt.excluded.is_complete,
            # Once set, a completion timestamp doesn't move on re-evaluation
            # (re-running the same job twice mustn't look like completing
            # twice) — only fill it in the first time `is_complete` flips true.
            "completed_at": func.coalesce(Progress.completed_at, stmt.excluded.completed_at),
            "updated_at": func.now(),
        },
    )
    await db.execute(stmt)


async def evaluate_event(db: AsyncSession, event: Event) -> None:
    """Re-evaluate every active challenge listening for `event.event_type`
    against `event.user_id`'s full event history, and persist the result.
    """
    stmt = select(Challenge).where(
        Challenge.event_type == event.event_type,
        Challenge.status == ChallengeStatus.active.value,
    )
    challenges = (await db.scalars(stmt)).all()

    for challenge in challenges:
        strategy = STRATEGIES[challenge.type]
        result = await strategy.evaluate(db, user_id=event.user_id, challenge=challenge)
        await _upsert_progress(
            db, user_id=event.user_id, challenge_id=challenge.id, result=result
        )
        if result.is_complete:
            # Idempotent regardless of how many times this challenge has
            # already been evaluated as complete (invariant #5) — the
            # unique constraint on (user, challenge, completion_key) is
            # what actually prevents a double payout, not this `if`.
            await disburse_reward(db, user_id=event.user_id, challenge=challenge)
