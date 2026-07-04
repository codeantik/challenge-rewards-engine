"""The one ingestion path (CLAUDE.md invariant #2).

Forum mutation handlers call `ingest_event` directly (an in-process function
call, not a second HTTP hop) so that the domain write and the event write
land in the *same* DB transaction — the caller still owns `commit()`. The
public `POST /api/events` endpoint calls this exact function too, plus
layers the `202` envelope on top. Nothing about this signature changed to
support that — extension, not a second code path.

This function also owns both idempotency-adjacent behaviours from
CLAUDE.md invariant #4/#5 for *event ingestion*:

- **Conflict replay**: if `event_id` already exists, we return the
  stored original row untouched (`is_new=False`) instead of reprocessing.
  Because the caller's response is built purely from the returned `Event`
  row's fields, replaying the same row is what makes a resubmission
  byte-identical to the original response.
- **Transactional job enqueue**: a genuinely new event enqueues exactly one
  `Job` row in the same transaction as the event insert — never on replay,
  so a doubled `event_id` never doubles evaluation work either.

The insert is wrapped in a `SAVEPOINT` (`begin_nested`) rather than letting
an `IntegrityError` propagate: forum handlers call this *after* already
flushing their own domain row (a `Post`, a `Comment`) in the same
outer transaction, and a plain `flush()`-raises-then-rollback would roll
back that domain row too. A savepoint confines the rollback to just this
event/job insert attempt.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.job import Job


async def ingest_event(
    db: AsyncSession,
    *,
    event_type: str,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    event_id: uuid.UUID | None = None,
) -> tuple[Event, bool]:
    """Returns `(event, is_new)`. `is_new` is `False` when `event_id` had
    already been seen — the caller should treat that as a replay, not a
    fresh acceptance.
    """
    event_id = event_id or uuid.uuid4()

    try:
        async with db.begin_nested():
            event = Event(
                event_id=event_id, event_type=event_type, user_id=user_id, payload=payload
            )
            db.add(event)
            await db.flush()
            db.add(Job(event_id=event_id))
            await db.flush()
    except IntegrityError:
        # Only a genuine event_id replay is expected here — anything else
        # (e.g. a bad user_id FK) is a real error and should keep propagating.
        existing = await db.get(Event, event_id)
        if existing is None:
            raise
        return existing, False

    return event, True
