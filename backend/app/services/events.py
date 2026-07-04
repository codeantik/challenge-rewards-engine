"""The one ingestion path (CLAUDE.md invariant #2).

Forum mutation handlers call `ingest_event` directly (an in-process function
call, not a second HTTP hop) so that the domain write and the event write
land in the *same* DB transaction — the caller still owns `commit()`. Phase 3
adds the public `POST /api/events` endpoint; it will call this exact
function too, plus layer on `event_id` conflict replay and the transactional
job-row enqueue. Nothing about this signature should need to change for
that — extension, not a second code path.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


async def ingest_event(
    db: AsyncSession,
    *,
    event_type: str,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    event_id: uuid.UUID | None = None,
) -> Event:
    event = Event(
        event_id=event_id or uuid.uuid4(),
        event_type=event_type,
        user_id=user_id,
        payload=payload,
    )
    db.add(event)
    await db.flush()
    return event
